# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# December 2 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"""Command to execute mutests."""

import asyncio
import logging
import os
import subprocess
import sys
import time

from argparse import ArgumentParser
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from typing import Union

from munet import mulog
from munet import parser
from munet.args import add_testing_args
from munet.base import Bridge
from munet.base import get_event_loop
from munet.cli import async_cli
from munet.compat import PytestConfig
from munet.mutest import userapi as uapi
from munet.native import L3NodeMixin
from munet.native import Munet
from munet.parser import async_build_topology
from munet.parser import get_config


# We want all but critical to fit in 5 characters for alignment
logging.addLevelName(logging.WARNING, "WARN")
root_logger = logging.getLogger("")
exec_formatter = logging.Formatter("%(asctime)s %(levelname)5s: %(name)s: %(message)s")


async def get_unet(
    config: dict, croot: Path, rundir: Path, args: Namespace, unshare: bool = False
):
    """Create and run a new Munet topology.

    The topology is built from the given ``config`` to run inside the path indicated
    by ``rundir``. If ``unshare`` is True then the process will unshare into it's
    own private namespace.

    Args:
        config: a config dictionary obtained from ``munet.parser.get_config``. This
          value will be modified and stored in the built ``Munet`` object.
        croot: common root of all tests, used to search for ``kinds.yaml`` files.
        rundir: the path to the run directory for this topology.
        args: argparse args
        unshare: True to unshare the process into it's own private namespace.

    Yields:
        Munet: The constructed and running topology.
    """
    tasks = []
    unet = None
    try:
        try:
            unet = await async_build_topology(
                config,
                rundir=str(rundir),
                args=args,
                pytestconfig=PytestConfig(args),
                unshare_inline=unshare,
            )
        except Exception as error:
            logging.debug("unet build failed: %s", error, exc_info=True)
            raise
        try:
            tasks = await unet.run()
        except Exception as error:
            logging.debug("unet run failed: %s", error, exc_info=True)
            raise
        logging.debug("unet topology running")
        try:
            yield unet
        except Exception as error:
            logging.error("unet fixture: yield unet unexpected exception: %s", error)
            raise
    except KeyboardInterrupt:
        logging.info("Received keyboard while building topology")
        raise
    finally:
        if unet:
            await unet.async_delete()

        # No one ever awaits these so cancel them
        logging.debug("unet fixture: cleanup")
        for task in tasks:
            task.cancel()

        # Reset the class variables so auto number is predictable
        logging.debug("unet fixture: resetting ords to 1")
        L3NodeMixin.next_ord = 1
        Bridge.next_ord = 1


def common_root(path1: Union[str, Path], path2: Union[str, Path]) -> Path:
    """Find the common root between 2 paths.

    Args:
        path1: Path
        path2: Path
    Returns:
        Path: the shared root components between ``path1`` and ``path2``.

    Examples:
        >>> common_root("/foo/bar/baz", "/foo/bar/zip/zap")
        PosixPath('/foo/bar')
        >>> common_root("/foo/bar/baz", "/fod/bar/zip/zap")
        PosixPath('/')
    """
    apath1 = Path(path1).absolute().parts
    apath2 = Path(path2).absolute().parts
    alen = min(len(apath1), len(apath2))
    common = None
    for a, b in zip(apath1[:alen], apath2[:alen]):
        if a != b:
            break
        common = common.joinpath(a) if common else Path(a)
    return common


async def collect(args: Namespace):
    """Collect test files.

    Files must match the pattern ``mutest_*.py``, and their containing
    directory must have a munet config file present. This function also changes
    the current directory to the common parent of all the tests, and paths are
    returned relative to the common directory.

    Args:
      args: argparse results

    Returns:
      (commondir, tests, configs): where ``commondir`` is the path representing
        the common parent directory of all the testsd, ``tests`` is a
        dictionary of lists of test files, keyed on their containing directory
        path, and ``configs`` is a dictionary of config dictionaries also keyed
        on its containing directory path. The directory paths are relative to a
        common ancestor.
    """
    file_select = args.file_select
    upaths = args.paths if args.paths else ["."]
    globpaths = set()
    for upath in (Path(x) for x in upaths):
        if upath.is_file():
            paths = {upath.absolute()}
        else:
            paths = {x.absolute() for x in Path(upath).rglob(file_select)}
        globpaths |= paths
    tests = {}
    configs = {}

    # Find the common root
    # We don't actually need this anymore, the idea was prefix test names
    # with uncommon paths elements to automatically differentiate them.
    common = None
    sortedpaths = []
    for path in sorted(globpaths):
        sortedpaths.append(path)
        dirpath = path.parent
        common = common_root(common, dirpath) if common else dirpath

    ocwd = Path().absolute()
    try:
        # We don't want to work with relative paths to the common directory since
        # The common directory may not end up containing the configuration file.
        for path in sortedpaths:
            dirpath = path.parent
            if dirpath not in configs:
                try:
                    configs[dirpath] = get_config(search=[dirpath])
                except FileNotFoundError:
                    try:
                        # For defining groups of tests, the config might be located in the parent
                        configs[dirpath] = get_config(search=[dirpath.parent])
                    except FileNotFoundError:
                        logging.warning(
                            "Skipping '%s' as munet.{yaml,toml,json} not found in '%s' or '%s'",
                            path,
                            dirpath,
                            dirpath.parent,
                        )
                        continue
            if dirpath not in tests:
                tests[dirpath] = []
            tests[dirpath].append(path.absolute())
    finally:
        os.chdir(ocwd)
    return common, tests, configs


async def execute_test(
    unet: Munet,
    test: Path,
    args: Namespace,
    tag: str,
    test_group_name: str,
    exec_handler: logging.Handler,
) -> (int, int, int, Exception):
    """Execute a test case script.

    Using the built and running topology in ``unet`` for targets
    execute the test case script file ``test``.

    Args:
        unet: a running topology.
        test: path to the test case script file.
        args: argparse results.
        tag: the identity of this test within a run. (x.x...)
        test_group_name: the name of the current running group for logging purposes.
        exec_handler: exec file handler to add to test loggers which do not propagate.
    """
    test_name = testname_from_path(test)

    # Get test case loggers
    logger = logging.getLogger(f"mutest.output.{test_group_name}")
    reslog = logging.getLogger(f"mutest.results.{test_group_name}")
    logger.addHandler(exec_handler)
    reslog.addHandler(exec_handler)

    # We need to send an info level log to cause the specific handler to be
    # created, otherwise all these debug ones don't get through
    reslog.info("")

    # reslog.debug("START: %s:%s from %s", tag, test_name, test.stem)
    # reslog.debug("-" * 70)

    targets = dict(unet.hosts.items())
    targets["."] = unet

    tc = uapi.TestCase(
        tag, test_name, test, targets, args, logger, reslog, args.full_summary
    )
    try:
        passed, failed, e = tc.execute()
    except uapi.CLIOnErrorError as error:
        if error.desc != "":
            print(f"\n== CLI ON ERROR: {error.desc} ==")
        else:
            print("\n== CLI ON ERROR: *NO DESCRIPTION PROVIDED* ==")
        await async_cli(unet)
        passed, failed, e = 0, 0, error

    run_time = time.time() - tc.info.start_time

    status = "PASS" if not (failed or e) else "FAIL"

    # Turn off for now
    reslog.debug("-" * 70)
    reslog.debug(
        "stats: %d steps, %d pass, %d fail, %s abort, %4.2fs elapsed",
        passed + failed,
        passed,
        failed,
        1 if e else 0,
        run_time,
    )
    reslog.debug("-" * 70)
    reslog.debug("END: %s %s:%s\n", status, tag, test_name)

    return passed, failed, e


def testname_from_path(path: Path) -> str:
    """Return test name based on the path to the test file.

    Args:
       path: path to the test file.

    Returns:
       str: the name of the test.
    """
    return str(Path(path).stem).replace("/", ".")


def print_header(reslog, unet):
    targets = dict(unet.hosts.items())
    nmax = max(len(x) for x in targets)
    nmax = max(nmax, len("TARGET"))
    sum_fmt = uapi.TestCase.sum_fmt.format(nmax)
    reslog.info(sum_fmt, "NUMBER", "STAT", "TARGET", "TIME", "DESCRIPTION")
    reslog.info("-" * 70)


async def run_tests(args):
    reslog = logging.getLogger("mutest.results")

    common, tests, configs = await collect(args)
    results = []
    errlog = logging.getLogger("mutest.error")
    reslog = logging.getLogger("mutest.results")
    printed_header = False
    snum = 0
    tnum = 0
    start_time = time.time()
    try:
        for dirpath in tests:
            if args.validate_only:
                parser.validate_config(configs[dirpath], reslog, args)
                continue

            test_files = tests[dirpath]
            test_groups = {}
            # Each mutest coexisting with their config file run in a separate
            #  group (and therefore, topology instance; backwards compatible!)
            # All other mutests are grouped into groups corresponding to their
            #  shared dirpath. All tests within the group share a topology instance.
            if str(dirpath.absolute()) in configs[dirpath]['config_pathname']:
                test_groups = {testname_from_path(test): [test] for test in test_files}
            else:
                assert dirpath.name != ''
                test_groups[dirpath.name] = [test for test in test_files]

            for test_group_name, test_group in test_groups.items():
                tnum = 0
                snum += 1
                config = deepcopy(configs[dirpath])
                rundir = args.rundir.joinpath(test_group_name)

                # Add an test case exec file handler to the root logger and result
                # logger
                exec_path = rundir.joinpath("mutest-exec.log")
                exec_path.parent.mkdir(parents=True, exist_ok=True)
                exec_handler = logging.FileHandler(exec_path, "w")
                exec_handler.setFormatter(exec_formatter)
                root_logger.addHandler(exec_handler)

                async for unet in get_unet(config, common, rundir, args):
                    for test in test_group:
                        tnum += 1
                        test_name = testname_from_path(test)
                        try:
                            if not printed_header:
                                print_header(reslog, unet)
                                printed_header = True

                            passed, failed, e = await execute_test(
                                unet, test, args, f"{snum}.{tnum}", test_group_name, exec_handler
                            )
                        except KeyboardInterrupt as error:
                            errlog.warning(
                                "KeyboardInterrupt while running group: %s, test: %s",
                                test_group_name,
                                test_name
                            )
                            passed, failed, e = 0, 0, error
                            raise
                        except Exception as error:
                            logging.error(
                                "Error executing test group %s, test %s: %s",
                                test_group_name,
                                test_name,
                                error,
                                exc_info=True,
                            )
                            errlog.error(
                                "Error executing test group %s, test %s: %s",
                                test_group_name,
                                test_name,
                                error,
                                exc_info=True,
                            )
                            passed, failed, e = 0, 0, error
                        finally:
                            # Remove the test case exec file handler form the root logger.
                            if test == test_group[-1]:
                                root_logger.removeHandler(exec_handler)
                            results.append((test_group_name, test_name, passed, failed, e))

    except KeyboardInterrupt:
        pass

    if args.validate_only:
        return False

    run_time = time.time() - start_time
    tpassed = 0
    tfailed = 0
    texc = 0

    spassed = 0
    sfailed = 0

    for result in results:
        _, _, passed, failed, e = result
        spassed += passed
        sfailed += failed
        if e:
            texc += 1
        if failed or e:
            tfailed += 1
        else:
            tpassed += 1

    reslog.info("")
    reslog.info(
        "run stats: %s steps, %s pass, %s fail, %s abort, %4.2fs elapsed",
        spassed + sfailed,
        spassed,
        sfailed,
        texc,
        run_time,
    )
    reslog.info("-" * 70)

    tnum = 0
    tgroup = 0
    last_group_name = ""
    for result in results:
        test_group_name, test_name, passed, failed, e = result
        if test_group_name != last_group_name:
            tgroup += 1
            tnum = 1
        else:
            tnum += 1
        last_group_name = test_group_name
        if failed or e:
            reslog.warning(" FAIL  %s:%s:%s", tgroup, tnum, test_name)
        else:
            reslog.info(" PASS  %s:%s:%s", tgroup, tnum, test_name)

    reslog.info("-" * 70)
    reslog.info(
        "END RUN: %s test scripts, %s passed, %s failed", len(results), tpassed, tfailed
    )

    return 1 if tfailed else 0


async def async_main(args):
    status = 3
    try:
        # For some reson we are not catching exceptions raised inside
        status = await run_tests(args)
    except KeyboardInterrupt:
        logging.info("Exiting (async_main), received KeyboardInterrupt in main")
    except Exception as error:
        logging.info(
            "Exiting (async_main), unexpected exception %s", error, exc_info=True
        )
    logging.debug("async_main returns %s", status)
    return status


def main():
    ap = ArgumentParser()
    ap.add_argument(
        "-v", dest="verbose", action="count", default=0, help="More -v's, more verbose"
    )
    ap.add_argument(
        "-V", "--version", action="store_true", help="print the verison number and exit"
    )
    ap.add_argument("paths", nargs="*", help="Paths to collect tests from")

    rap = ap.add_argument_group(title="Runtime", description="runtime related options")
    rap.add_argument(
        "-d", "--rundir", help="runtime directory for tempfiles, logs, etc"
    )
    add_testing_args(rap.add_argument)

    eap = ap.add_argument_group(title="Uncommon", description="uncommonly used options")
    eap.add_argument(
        "--file-select", default="mutest_*.py", help="shell glob for finding tests"
    )
    eap.add_argument(
        "--full-summary",
        action="store_true",
        help="print full summary headers from docstrings",
    )
    eap.add_argument("--log-config", help="logging config file (yaml, toml, json, ...)")
    eap.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the munet configs against the schema definition",
    )

    args = ap.parse_args()

    if args.version:
        from importlib import metadata  # pylint: disable=C0415

        print(metadata.version("munet"))
        sys.exit(0)

    rundir = args.rundir if args.rundir else "/tmp/mutest"
    rundir = Path(rundir).absolute()
    args.rundir = rundir
    os.environ["MUNET_RUNDIR"] = str(rundir)
    subprocess.run(f"mkdir -p {rundir} && chmod 755 {rundir}", check=True, shell=True)

    config = parser.setup_logging(args, config_base="logconf-mutest")
    # Grab the exec formatter from the logging config
    if fconfig := config.get("formatters", {}).get("exec"):
        global exec_formatter  # pylint: disable=W291,W0603
        exec_formatter = logging.Formatter(
            fconfig.get("format"), fconfig.get("datefmt")
        )

    if not hasattr(sys.stderr, "isatty") or not sys.stderr.isatty():
        mulog.do_color = False

    loop = None
    status = 4
    try:
        loop = get_event_loop()
        status = loop.run_until_complete(async_main(args))
    except KeyboardInterrupt:
        logging.info("Exiting (main), received KeyboardInterrupt in main")
    except Exception as error:
        logging.info("Exiting (main), unexpected exception %s", error, exc_info=True)
    finally:
        if loop:
            loop.close()

    sys.exit(status)


if __name__ == "__main__":
    main()

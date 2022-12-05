# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 2 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; see the file COPYING; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
"""Command to execute mutests"""

import argparse
import asyncio
import functools
import logging
import os
import subprocess

from copy import deepcopy
from pathlib import Path
from typing import Union

from munet import parser
from munet.base import Bridge
from munet.lutil import luCommand2
from munet.lutil import luFinish
from munet.lutil import luInclude2
from munet.lutil import luStart
from munet.native import L3Node
from munet.parser import async_build_topology
from munet.parser import get_config


async def get_unet(config: dict, rundir: Union[str, Path], unshare: bool = True):
    """Create and run a new Munet topology.

    The topology is built from the given ``config`` to run inside the path indicated
    by ``rundir``. If ``unshare`` is True then the process will unshare into it's
    own private namespace.

    Args:
        config: a config dictionary obtained from ``munet.parser.get_config``. This
          value will be modified and stored in the built ``Munet`` object.
        rundir: the path to the run directory for this topology.
        unshare: True to unshare the process into it's own private namespace.
    Yields:
        Munet: The constructed and running topology.
    """
    try:
        unet = await async_build_topology(config, rundir=rundir, unshare_inline=unshare)
    except Exception as error:
        logging.debug("unet build failed: %s", error, exc_info=True)
        raise

    try:
        tasks = await unet.run()
    except Exception as error:
        logging.debug("unet run failed: %s", error, exc_info=True)
        await unet.async_delete()
        raise

    logging.debug("unet topology running")

    # Pytest is supposed to always return even if exceptions
    try:
        yield unet
    except Exception as error:
        logging.error("unet fixture: yield unet unexpected exception: %s", error)

    await unet.async_delete()

    # No one ever awaits these so cancel them
    logging.debug("unet fixture: cleanup")
    for task in tasks:
        task.cancel()

    # Reset the class variables so auto number is predictable
    logging.debug("unet fixture: resetting ords to 1")
    L3Node.next_ord = 1
    Bridge.next_ord = 1


def common_root(path1: Union[str, Path], path2: Union[str, Path]) -> Path:
    """Find the common root between 2 paths

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


async def collect(args):
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
    file_select = "mutest_*.py"
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
        os.chdir(common)
        # Work with relative paths to the common directory
        for path in (x.relative_to(common) for x in sortedpaths):
            dirpath = path.parent
            if dirpath not in configs:
                try:
                    configs[dirpath] = get_config(search=[dirpath])
                except FileNotFoundError:
                    logging.warning(
                        "Skipping '%s' as munet.{yaml,toml,json} not found in '%s'",
                        path,
                        dirpath,
                    )
                    continue
            if dirpath not in tests:
                tests[dirpath] = []
            tests[dirpath].append(path.absolute())
    finally:
        os.chdir(ocwd)
    return common, tests, configs


async def execute_test(unet, test, args):  # pylint: disable=W0613
    test_name = testname_from_path(test)
    script = open(f"{test}", "r", encoding="utf-8").read()

    outlog = logging.getLogger(f"mutest.output.{test_name}.output")
    reslog = logging.getLogger(f"mutest.results.{test_name}.result")
    reslog.info("=" * 70)
    reslog.info("EXEC: %s", test_name)
    reslog.info("-" * 70)

    testdata = luStart(
        unet.hosts,
        outlog=outlog,
        reslog=reslog,
        level=5,  # make this depend on -vvv
    )
    luCommand = functools.partial(luCommand2, testdata)  # pylint: disable=W0641
    luInclude = functools.partial(luInclude2, testdata)  # pylint: disable=W0641
    try:
        exec(script, globals(), locals())  # pylint: disable=W0122
        # assert testdata.l_fail == 0, \
        #     f"{test_name} FAIL: steps passed: {{testdata.l_pass}}"
        #       " failed: {{testdata.l_fail}}"
    except Exception as error:
        logging.error("Unexpected exception during test %s: %s", test_name, error)
    finally:
        # result = "FAIL" if testdata.l_fail else "PASS"
        luFinish(testdata)


def testname_from_path(path: Union[str, Path]) -> str:
    """Return test name based on the path to the test file.

    Args:
       path: path to the test file.

    Returns:
        str: the name of the test.

    """
    return str(Path(path).stem).replace("/", ".")


async def async_main(args):
    _, tests, configs = await collect(args)
    for dirpath in tests:
        test_files = tests[dirpath]
        for test in test_files:
            config = deepcopy(configs[dirpath])
            test_name = testname_from_path(test)
            rundir = os.path.join("/tmp/unet-mutest", test_name)
            async for unet in get_unet(config, rundir):
                try:
                    await execute_test(unet, test, args)
                except Exception as error:
                    logging.error(
                        "Unexpected exception in execute_test: %s", error, exc_info=True
                    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dist",
        type=int,
        nargs="?",
        const=-1,
        default=0,
        action="store",
        metavar="NUM-THREADS",
        help="Run in parallel, value is num. of threads or no value for auto",
    )
    ap.add_argument("-d", "--rundir", help="runtime directory for tempfiles, logs, etc")
    ap.add_argument("--log-config", help="logging config file (yaml, toml, json, ...)")
    ap.add_argument(
        "-v", dest="verbose", action="count", default=0, help="More -v's, more verbose"
    )
    ap.add_argument("paths", nargs="*", help="Paths to collect tests from")
    args = ap.parse_args()

    rundir = args.rundir if args.rundir else "/tmp/unet-mutest"
    args.rundir = rundir
    os.environ["MUNET_RUNDIR"] = rundir
    subprocess.run(f"mkdir -p {rundir} && chmod 755 {rundir}", check=True, shell=True)
    parser.setup_logging(args, config_base="logconf-mutest")

    status = 4
    try:
        status = asyncio.run(async_main(args))
    except KeyboardInterrupt:
        logging.info("Exiting, received KeyboardInterrupt in main")
    except Exception as error:
        logging.info("Exiting, unexpected exception %s", error, exc_info=True)

    return status


if __name__ == "__main__":
    main()

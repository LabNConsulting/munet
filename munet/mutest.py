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
"""Command to execute setests"""

import argparse
import asyncio
import logging
import os

from copy import deepcopy
from pathlib import Path

from munet.base import Bridge
from munet.native import L3Node
from munet.parser import async_build_topology
from munet.parser import get_config


async def get_unet(config, rundir, unshare=True):
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


def common_root(path1, path2):
    """Find the common root between 2 paths

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

    Files must match the pattern ``setest_*.py``, and their containing
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
    file_select = "setest_*.py"
    upaths = args.paths if args.paths else ["."]
    for upath in upaths:
        globpaths = {x.absolute() for x in Path(upath).rglob(file_select)}
    tests = {}
    configs = {}

    # Find the common root
    common = None
    for upath in upaths:
        globpaths = {x.absolute() for x in Path(upath).rglob(file_select)}
        for path in globpaths:
            dirpath = path.parent
            common = common_root(common, dirpath) if common else dirpath

    ocwd = Path().absolute()
    try:
        os.chdir(common)
        # Work with relative paths to the common directory
        for path in (x.relative_to(common) for x in globpaths):
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
            tests[dirpath].append(path)
    finally:
        os.chdir(ocwd)
    return common, tests, configs


async def execute_test(unet, test, args):  # pylint: disable=W0613
    logging.info("EXEC test %s", test)


async def async_main(args):
    _, tests, configs = await collect(args)
    for dirpath in tests:
        test_files = tests[dirpath]
        for test in test_files:
            config = deepcopy(configs[dirpath])
            test_name = str(test.stem).replace("/", ".")
            rundir = os.path.join("/tmp/unet-setest", test_name)
            async for unet in get_unet(config, rundir):
                try:
                    await execute_test(unet, test, args)
                except Exception as error:
                    logging.error(
                        "Unexpected exception in execute_test: %s", error, exc_info=True
                    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dist",
        type=int,
        nargs="?",
        const=-1,
        default=0,
        action="store",
        metavar="NUM-THREADS",
        help="Run in parallel, value is num. of threads or no value for auto",
    )
    parser.add_argument(
        "-v", dest="verbose", action="count", default=0, help="More -v's, more verbose"
    )
    parser.add_argument("paths", nargs="*", help="Paths to collect tests from")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s: %(message)s")

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

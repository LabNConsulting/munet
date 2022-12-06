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
import logging

from munet.base import commander


def use_pytest(args):
    pytest = commander.get_exec_path("pytest")

    oargs = [
        "-c",
        "none",
        "-s",
        "-q",
        # "--no-header",
        # "--no-summary",
        # "--show-capture=no",
        # '--log-format="XXX %(asctime)s %(levelname)s %(message)s"',
        # '--log-file-format="XXX %(asctime)s %(levelname)s %(message)s"',
        # "--log-file=mutest-log.txt",
        # "--log-level=DEBUG",
        '--junit-xml="mutest-results.xml"',
        "--override-ini=asyncio_mode=auto",
        '--override-ini=python_functions="setest*"',
    ]
    if args.dist:
        oargs.append("--dist=load")
        if args.dist == -1:
            oargs.append("-nauto")
        else:
            oargs.append(f"-n{args.dist}")

    if not args.verbose:
        oargs.append("--log-cli-level=CRITICAL")
    else:
        oargs.append("-v")
        if args.verbose > 2:
            oargs.append("--log-cli-level=DEBUG")
        elif args.verbose > 1:
            oargs.append("--log-cli-level=INFO")
        else:
            oargs.append("--log-cli-level=WARNING")
    if args.paths:
        oargs += args.paths
    commander.cmd_status(
        [pytest, *oargs],
        warn=False,
        stdin=None,
        stdout=None,
        stderr=None,
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

    use_pytest(args)


if __name__ == "__main__":
    main()

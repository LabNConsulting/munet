# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# September 2 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
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
import argparse
import logging
import sys
import time

from . import parser
from .cli import cli
from .cleanup import cleanup_previous

logger = logging.getLogger(__name__)


def run(args, config, unet):
    """Run the node commands in the topology"""
    return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", action="store_true", help="Run the CLI")
    ap.add_argument("-c", "--config", help="config file (yaml, toml, json, ...)")
    ap.add_argument(
        "--no-cleanup", action="store_true", help="Do not cleanup previous runs"
    )
    ap.add_argument("--no-wait", action="store_true", help="Exit after commands")
    ap.add_argument(
        "--topology-only",
        action="store_true",
        help="Do not run any node commands",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="be verbose")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    config = parser.get_config(args.config)
    if not config["topology"]["nodes"]:
        logging.critical("No nodes defined in config file")
        return 1

    if not args.no_cleanup:
        cleanup_previous()
    unet = parser.build_topology(config, logger)
    try:
        logging.info("Topology up")

        if not args.topology_only:
            run(args, config, unet)

        if sys.stdin.isatty():
            cli(unet)

        if not args.no_wait:
            logging.info("Waiting on signal to exit")
            while True:
                time.sleep(3600)
    finally:
        unet.delete()
    return 0


sys.exit(main())

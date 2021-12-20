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
import asyncio
import logging
import logging.config
import os
import subprocess
import sys

from . import cli
from . import parser
from .cleanup import cleanup_previous


logger = None


async def forever():
    while True:
        await asyncio.sleep(3600)


async def run_and_wait(args, unet):
    tasks = []

    if not args.topology_only:
        # add the cmd.wait()s returned from unet.run()
        tasks += await unet.run()

    if sys.stdin.isatty() and not args.no_cli:
        # Run an interactive CLI
        task = asyncio.create_task(cli.async_cli(unet))
    else:
        if args.no_wait:
            logger.info("Waiting for all node cmd to complete")
        else:
            logger.info("Waiting on signal to exit")
            task = asyncio.create_task(forever())
        task = asyncio.gather(task, *tasks, return_exceptions=True)

    await task


async def async_main(args, unet):
    status = 3
    try:
        status = await run_and_wait(args, unet)
    except KeyboardInterrupt:
        logger.info("Exiting, received KeyboardInterrupt in async_main")
    except asyncio.CancelledError as ex:
        logger.info("task canceled error: %s cleaning up", ex)
    except Exception as error:
        logger.info("Exiting, unexpected exception %s", error, exc_info=True)
    else:
        logger.info("Exiting normally")

    try:
        if unet:
            logger.debug("main: async deleting")
            await unet.async_delete()
    except Exception as error:
        status = 2
        logger.info("Deleting, unexpected exception %s", error, exc_info=True)

    return status


def main(*args):
    ap = argparse.ArgumentParser(args)
    ap.add_argument("-c", "--config", help="config file (yaml, toml, json, ...)")
    ap.add_argument("--kinds-config", help="kinds config file (yaml, toml, json, ...)")
    ap.add_argument(
        "--host",
        action="store_true",
        help="no isolation for top namespace, bridges exposed to default namespace",
    )
    ap.add_argument("--log-config", help="logging config file (yaml, toml, json, ...)")
    ap.add_argument(
        "--no-cleanup", action="store_true", help="Do not cleanup previous runs"
    )
    ap.add_argument(
        "--no-cli", action="store_true", help="Do not run the interactive CLI"
    )
    ap.add_argument("--no-wait", action="store_true", help="Exit after commands")
    ap.add_argument("-d", "--rundir", help="runtime directory for tempfiles, logs, etc")
    ap.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the config against the schema definition",
    )
    ap.add_argument(
        "--topology-only",
        action="store_true",
        help="Do not run any node commands",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="be verbose")
    args = ap.parse_args()

    rundir = args.rundir if args.rundir else "/tmp/unet-" + os.environ["USER"]
    subprocess.run(f"mkdir -p {rundir} && chmod 755 {rundir}", check=True, shell=True)
    args.rundir = rundir

    os.environ["MUNET_RUNDIR"] = rundir

    parser.setup_logging(args)
    global logger  # pylint: disable=W0603
    logger = logging.getLogger("main")

    config = parser.get_config(args.config)
    logger.info("Loaded config from %s", config["config_pathname"])
    if not config["topology"]["nodes"]:
        logger.critical("No nodes defined in config file")
        return 1

    if not args.no_cleanup:
        cleanup_previous()

    status = 4
    unet = None
    try:
        if args.validate_only:
            return parser.validate_config(config, logger, args)

        # Setup the namespaces and network addressing.
        unet = parser.build_topology(config, rundir=args.rundir, args=args)
        logger.info("Topology up: rundir: %s", unet.rundir)

        # Executes the cmd for each node.
        status = asyncio.run(async_main(args, unet))
    except KeyboardInterrupt:
        logger.info("Exiting, received KeyboardInterrupt in main")
    except Exception as error:
        logger.info("Exiting, unexpected exception %s", error, exc_info=True)

    return status


if __name__ == "__main__":
    exit_status = main()
    sys.exit(exit_status)

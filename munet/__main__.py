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
import functools
import logging
import logging.config
import signal
import subprocess
import sys
import tempfile

from . import cli
from . import parser
from .cleanup import cleanup_previous
from .native import L3Node
from .native import to_thread


# logger = logging.getLogger("main")

ign_signals = {
    signal.SIGCONT,
    signal.SIGIO,
    signal.SIGPIPE,  # right to ignore?
    # signal.SIGTTIN,
    # signal.SIGTTOU,
    signal.SIGURG,
    signal.SIGUSR1,
    signal.SIGUSR2,
    signal.SIGWINCH,
}
exit_signals = {
    signal.SIGHUP,
    # signal.SIGINT,
    signal.SIGQUIT,
    signal.SIGTERM,
}
fail_signals = {
    signal.SIGABRT,
    signal.SIGBUS,
    signal.SIGFPE,
    signal.SIGILL,
    signal.SIGPWR,
    signal.SIGSEGV,
    signal.SIGSYS,
    signal.SIGXCPU,
    signal.SIGXFSZ,
}


class ExitSignalError(BaseException):
    pass


class FailSignalError(BaseException):
    pass


async def forever():
    while True:
        await asyncio.sleep(3600)


def setup_signals(tasklist):
    loop = asyncio.get_running_loop()

    def raise_signal(signum, fail):
        logger.critical(
            "Caught SIGNAL %s: %s", signum, signal.strsignal(signum), stack_info=fail
        )
        for task in tasklist:
            task.cancel()

    for sn in signal.valid_signals():
        h = signal.getsignal(sn)
        is_handled = h and h not in {signal.SIG_IGN, signal.SIG_DFL}
        if is_handled:
            if sn != signal.SIGINT:
                logger.warning(
                    "skipping python handled signum %s %s", sn, signal.strsignal(sn)
                )
        elif sn in ign_signals and is_handled != signal.SIG_IGN:
            try:
                signal.signal(sn, signal.SIG_IGN)
            except Exception as e:
                logger.debug("exception trying to ignore signal %s: %s", sn, e)
        elif sn in exit_signals or sn in fail_signals:
            loop.add_signal_handler(
                sn, functools.partial(raise_signal, sn, sn in fail_signals)
            )
        elif not (
            hasattr(signal, "SIGRTMIN")
            and hasattr(signal, "SIGRTMAX")
            and signal.SIGRTMIN <= sn <= signal.SIGRTMAX
        ):
            logger.debug(
                "doing nothing for signum %s %s (%s)", sn, signal.strsignal(sn), h
            )


async def async_main(args, unet):

    tasks = []

    setup_signals(tasks)
    try:
        if not args.topology_only:
            tasks.extend(await unet.run())

        if sys.stdin.isatty() and not args.no_cli:
            # Run an interactive CLI
            task = asyncio.create_task(cli.async_cli(unet))
            tasks.append(task)
        elif not args.no_wait:
            logger.info("Waiting on signal to exit")
            task = asyncio.create_task(forever())
            tasks.append(task)
        else:
            # Wait on our tasks
            logger.info("Waiting for all node cmd to complete")
            task = asyncio.gather(*tasks)
        await task
    except asyncio.CancelledError as ex:
        logger.info("Exiting, task canceled: %s tasks: %s", ex, tasks)
        return 1
    logger.info("Exiting normally")
    return 0


def main(*args):
    ap = argparse.ArgumentParser(args)
    ap.add_argument("--cli", action="store_true", help="Run the CLI")
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
        "--topology-only",
        action="store_true",
        help="Do not run any node commands",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="be verbose")
    args = ap.parse_args()

    rundir = args.rundir if args.rundir else tempfile.mkdtemp(prefix="unet")
    subprocess.run(f"mkdir -p {rundir} && chmod 755 {rundir}", check=True, shell=True)
    args.rundir = rundir

    parser.setup_logging(args)
    global logger
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
        # Setup the namespaces and network addressing.
        unet = parser.build_topology(config, rundir=args.rundir, args=args)
        logger.info("Topology up: rundir: %s", unet.rundir)

        status = 3
        # Executes the cmd for each node.
        status = asyncio.run(async_main(args, unet))
    except KeyboardInterrupt:
        logger.info("Exiting, received KeyboardInterrupt")
    except ExitSignalError as error:
        logger.info("Exiting, received ExitSignalError: %s", error)
    except Exception as error:
        logger.info("Exiting, unexpected exception %s", error, exc_info=True)

    try:
        logger.debug("main: async deleting")
        if unet:
            asyncio.run(unet.async_delete(), debug=True)
    except Exception as error:
        status = 2
        logger.info("Deleting, unexpected exception %s", error, exc_info=True)

    return status


if __name__ == "__main__":
    exit_status = main()
    sys.exit(exit_status)

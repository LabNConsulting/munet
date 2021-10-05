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
import os
import signal
import subprocess
import sys
import tempfile

from . import cli
from . import parser
from .cleanup import cleanup_previous
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
    signal.SIGINT,
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
        if is_handled and sn != signal.SIGINT:
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

            def log_cmd_result(node, future):
                try:
                    n = future.result()
                    logger.info("%s: cmd completed result: %s", node.name, n)
                except asyncio.CancelledError:
                    logger.info("%s: cmd.wait() canceled", future)

            procs = []
            for node in unet.hosts.values():
                p = await node.run_cmd()
                procs.append(p)
                task = asyncio.create_task(p.wait(), name=f"Node-{node.name}-cmd")
                task.add_done_callback(functools.partial(log_cmd_result, node))
                tasks.append(task)

        # tasks = []
        if sys.stdin.isatty() and not args.no_cli:
            # Run an interactive CLI
            coro = asyncio.create_task(to_thread(lambda: cli.cli(unet)))
            tasks.append(coro)
        elif not args.no_wait:
            logger.info("Waiting on signal to exit")
            coro = asyncio.create_task(forever())
            tasks.append(coro)
        else:
            # Wait on our tasks
            logger.info("Waiting for all node cmd to complete")
            coro = asyncio.gather(*tasks)
        await coro
    except asyncio.CancelledError as ex:
        logger.info("Exiting, task canceled: %s tasks: %s", ex, tasks)
        return 1
    logger.info("Exiting normally")
    return 0


def main(*args):
    ap = argparse.ArgumentParser(args)
    ap.add_argument("--cli", action="store_true", help="Run the CLI")
    ap.add_argument("-c", "--config", help="config file (yaml, toml, json, ...)")
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

    config, fname = parser.get_config(args.config)
    logger.info("Loaded config from %s/%s", os.getcwd(), fname)
    if not config["topology"]["nodes"]:
        logger.critical("No nodes defined in config file")
        return 1

    if not args.no_cleanup:
        cleanup_previous()

    # unet = parser.build_topology(config, logger, args.rundir)
    unet = parser.build_topology(config, rundir=args.rundir)
    logger.info("Topology up: rundir: %s", unet.rundir)

    status = 2
    try:
        status = asyncio.run(async_main(args, unet))
    except KeyboardInterrupt:
        logger.info("Exiting, received KeyboardInterrupt")
    except ExitSignalError as error:
        logger.info("Exiting, received ExitSignalError: %s", error)
    except Exception as error:
        logger.info("Exiting, received unexpected exception %s", error, exc_info=True)

    logger.info("Deleting unet")
    unet.delete()
    return status


if __name__ == "__main__":
    exit_status = main()
    sys.exit(exit_status)

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# January 28 2023, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2023, LabN Consulting, L.L.C.
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
"""A tiny init for namespaces in python inspired by the C program tini"""
import argparse
import logging
import os
import shlex
import signal
import subprocess
import sys
import time

from pathlib import Path
from signal import Signals as S


child_pid = -1
very_verbose = False

ignored_signals = {
    S.SIGTTIN,
    S.SIGTTOU,
}
handled_signals = {
    S.SIGCHLD,
}
abort_signals = {
    S.SIGABRT,
    S.SIGBUS,
    S.SIGFPE,
    S.SIGILL,
    S.SIGKILL,
    S.SIGSEGV,
    S.SIGSTOP,
    S.SIGSYS,
    S.SIGTRAP,
}
no_prop_signals = abort_signals | handled_signals | ignored_signals

restore_signals = set()


def vdebug(*args, **kwargs):
    if very_verbose:
        logging.debug(*args, **kwargs)


def sig_transit(signum, frame):
    logging.debug("Signalling child %s: %s", child_pid, signal.Signals(signum).name)
    try:
        # Kill the process group
        os.kill(child_pid, signum)
    except Exception as error:
        logging.warning("Got exception trying to forward signal: %s", error)


def sig_handle(signum, frame):
    assert signum == S.SIGCHLD

    try:
        pid, status = os.waitpid(-1, os.WNOHANG)
        if not pid:
            logging.warning("Got SIGCHLD but no pid to wait on")
            return

        try:
            if pid != child_pid:
                logging.debug("Reaped zombie pid %s with status %s", pid, status)
                return
            ec = os.waitstatus_to_exitcode(status)
            logging.debug("Reaped our child, exiting %s", ec)
            sys.exit(ec)
        except ValueError:
            vdebug("pid %s didn't actually exit", pid)

    except ChildProcessError as error:
        logging.warning("Got SIGCHLD but no pid to wait on: %s", error)


def setup_signals():
    valid = set(signal.valid_signals())
    named = set(x.value for x in signal.Signals)
    for snum in sorted(named):
        if snum not in valid:
            continue
        if S.SIGRTMIN <= snum <= S.SIGRTMAX:
            continue

        sname = signal.Signals(snum).name
        if snum in handled_signals:
            restore_signals.add(snum)
            vdebug("Installing local handler for %s", sname)
            signal.signal(snum, sig_handle)
        elif snum in ignored_signals:
            restore_signals.add(snum)
            vdebug("Installing ignore handler for %s", sname)
            signal.signal(snum, signal.SIG_IGN)
        elif snum in abort_signals:
            vdebug("Leaving default handler for %s", sname)
            # signal.signal(snum, signal.SIG_DFL)
            pass
        else:
            restore_signals.add(snum)
            vdebug("Installing transit signal handler for %s", sname)
            try:
                signal.signal(snum, sig_transit)
            except OSError as error:
                logging.warning(
                    "Failed installing signal handler for %s: %s", sname, error
                )
                pass


def run(exec_args):
    global child_pid

    setup_signals()

    child_pid = os.fork()
    if child_pid == 0:
        # Restore signals to default handling:
        for snum in restore_signals:
            signal.signal(snum, signal.SIG_DFL)

        estring = shlex.join(exec_args)
        try:
            # Block these in order to allow foregrounding below
            signal.signal(S.SIGTTIN, signal.SIG_IGN)
            signal.signal(S.SIGTTOU, signal.SIG_IGN)

            stdin_fd = sys.stdin.fileno()
            pid = os.getpid()
            os.setpgid(pid, 0)
            try:
                os.tcsetpgrp(stdin_fd, pid)
            except Exception as error:
                logging.warning("CHILD: unable to foreground pgid: %s", error)

            # unblock now
            signal.signal(S.SIGTTIN, signal.SIG_DFL)
            signal.signal(S.SIGTTOU, signal.SIG_DFL)

            # and exec the process
            logging.debug("CHILD: executing '%s'", estring)
            os.execvp(exec_args[0], exec_args)
            # NORETURN
        except Exception as error:
            logging.warning("CHILD: unable to execute '%s': %s", estring, error)
            raise

    logging.debug("waiting for child to exit")
    while True:
        time.sleep(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--pidfile", help="File to write child pid to.")
    ap.add_argument(
        "-v", dest="verbose", action="count", default=0, help="More -v's, more verbose"
    )
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    if args.verbose > 1:
        global very_verbose
        very_verbose = True
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s: %(message)s")

    status = 4
    try:
        run(args.rest)
    except KeyboardInterrupt:
        logging.info("Exiting (main), received KeyboardInterrupt in main")
    except Exception as error:
        logging.info("Exiting (main), unexpected exception %s", error, exc_info=True)

    sys.exit(status)


if __name__ == "__main__":
    main()

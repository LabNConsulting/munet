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
"""A tiny init for namespaces in python inspired by the C program tini."""

# pylint: disable=global-statement
import argparse
import errno
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
import time

from signal import Signals as S

from munet import linux


child_pid = -1
very_verbose = False
restore_signals = set()
g_exit_signal = False
g_pid_status_cache = {}


logquit_signals = {
    S.SIGHUP,
    S.SIGINT,
    S.SIGQUIT,
    S.SIGTERM,
}
ignored_signals = {
    S.SIGTTIN,
    S.SIGTTOU,
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
no_prop_signals = abort_signals | ignored_signals | {S.SIGCHLD}


def vdebug(*args, **kwargs):
    if very_verbose:
        logging.debug(*args, **kwargs)


def get_status_item(status, stat):
    m = re.search(rf"(?:^|\n){stat}:\t(.*)(?:\n|$)", status)
    return m.group(1).strip() if m else None


def pget_status_item(pid, stat):
    if pid not in g_pid_status_cache:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as f:
            g_pid_status_cache[pid] = f.read().strip()
    return get_status_item(g_pid_status_cache[pid], stat).strip()


def get_child_pids():
    g_pid_status_cache.clear()
    pids = (int(x) for x in os.listdir("/proc") if x.isdigit() and x != "1")
    return (x for x in pids if x == child_pid or pget_status_item(x, "PPid") == "0")


def check_exit(signame):
    if not g_exit_signal:
        logging.info("Exit flag not set, not checking for exit")
        return

    pids = list(get_child_pids())
    if not pids:
        logging.info("Exiting on %s, no children left", signame)
        sys.exit(0)

    logging.info("Exit flag set but %s pids left (%s)", len(pids), pids)


def waitpid(tag):
    logging.debug("%s: waitid for exiting process", tag)
    idobj = os.waitid(os.P_ALL, 0, os.WEXITED)
    pid = idobj.si_pid
    status = idobj.si_status
    logging.debug("%s: reaped zombie pid %s with status %s", tag, pid, status)

    # If our child exited then we are just waiting for the rest to go before we do
    if child_pid == pid:
        logging.debug("child exited, set mutini exit signal flag")
        global g_exit_signal
        g_exit_signal = True

    check_exit(tag)


def sig_trasmit(signum, _):
    global g_exit_signal

    signame = signal.Signals(signum).name
    if signum in logquit_signals:
        logging.debug("got transmit signal %s, set mutini exit signal flag", signame)
        g_exit_signal = True

    try:
        #
        # Signal all "children" (0 ppid or ours)
        #
        for pid in sorted(get_child_pids()):
            pidname = get_status_item(g_pid_status_cache[pid], "Name")
            logging.debug("%s child pid %s (%s)", signame, pid, pidname)
            os.kill(pid, signum)
    except OSError as error:
        if error.errno == errno.ESRCH:
            logging.info("No process to send signal to, quiting")
            ec = os.waitstatus_to_exitcode(-signum)
            sys.exit(ec)
        logging.warning("got exception trying to forward signal: %s", error)
    except Exception as error:
        logging.warning("got exception trying to forward signal: %s", error)

    check_exit(signame)


def sig_sigchld(signum, _):
    assert signum == S.SIGCHLD
    try:
        waitpid("SIGCHLD")
    except ChildProcessError as error:
        logging.warning("got SIGCHLD but no pid to wait on: %s", error)

    check_exit("SIGCHLD")


def setup_signals():
    valid = set(signal.valid_signals())
    named = set(x.value for x in signal.Signals)
    for snum in sorted(named):
        if snum not in valid:
            continue
        if S.SIGRTMIN <= snum <= S.SIGRTMAX:
            continue

        sname = signal.Signals(snum).name
        if snum == S.SIGCHLD:
            restore_signals.add(snum)
            vdebug("installing local handler for %s", sname)
            signal.signal(snum, sig_sigchld)
        elif snum in ignored_signals:
            restore_signals.add(snum)
            vdebug("installing ignore handler for %s", sname)
            signal.signal(snum, signal.SIG_IGN)
        elif snum in abort_signals:
            vdebug("leaving default handler for %s", sname)
            # signal.signal(snum, signal.SIG_DFL)
        else:
            restore_signals.add(snum)
            vdebug("installing trasmit signal handler for %s", sname)
            try:
                signal.signal(snum, sig_trasmit)
            except OSError as error:
                logging.warning(
                    "failed installing signal handler for %s: %s", sname, error
                )


def new_process_group():
    pid = os.getpid()
    try:
        pgid = os.getpgrp()
        if pgid == pid:
            logging.debug("already process group leader %s", pgid)
        else:
            logging.debug("creating new process group %s", pid)
            os.setpgid(pid, 0)
    except Exception as error:
        logging.warning("unable to get new process group: %s", error)
        return

    # Block these in order to allow foregrounding, otherwise we'd get SIGTTOU blocked
    signal.signal(S.SIGTTIN, signal.SIG_IGN)
    signal.signal(S.SIGTTOU, signal.SIG_IGN)
    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        logging.debug("stdin not a tty no foregrounding required")
    else:
        try:
            # This will error if our session no longer associated with controlling tty.
            pgid = os.tcgetpgrp(fd)
            if pgid == pid:
                logging.debug("process group already in foreground %s", pgid)
            else:
                logging.debug("making us the foreground pgid backgrounding %s", pgid)
                os.tcsetpgrp(fd, pid)
        except OSError as error:
            if error.errno == errno.ENOTTY:
                logging.debug("session is no longer associated with controlling tty")
            else:
                logging.warning("unable to foreground pgid %s: %s", pid, error)
    signal.signal(S.SIGTTIN, signal.SIG_DFL)
    signal.signal(S.SIGTTOU, signal.SIG_DFL)


def exec_child(exec_args):
    # Restore signals to default handling:
    for snum in restore_signals:
        signal.signal(snum, signal.SIG_DFL)

    # Create new process group.
    new_process_group()

    estring = shlex.join(exec_args)
    try:
        # and exec the process
        logging.debug("child: executing '%s'", estring)
        os.execvp(exec_args[0], exec_args)
        # NOTREACHED
    except Exception as error:
        logging.warning("child: unable to execute '%s': %s", estring, error)
        raise


def is_creating_pid_namespace():
    p1name = subprocess.check_output(
        "readlink /proc/self/pid", stderr=subprocess.STDOUT, shell=True
    )
    p2name = subprocess.check_output(
        "readlink /proc/self/pid_for_children", stderr=subprocess.STDOUT, shell=True
    )
    return p1name != p2name


def run(new_pg, exec_args):
    global child_pid  # pylint: disable=global-statement

    #
    # Arrange for us to be killed when our parent dies, this will subsequently also kill
    # all procs in any PID namespace we are init for.
    #
    linux.set_parent_death_signal(signal.SIGKILL)

    # Set (parent) signal handlers before fork to avoid race
    # for non-exec case we'll log the signal and exit.
    setup_signals()

    # If we are createing a new PID namespace for children...
    pid = os.getpid()
    if pid != 1:
        logging.debug("started as pid %s not pid 1", pid)
        if not is_creating_pid_namespace():
            raise Exception("mutini must be (or able to become) pid 1 for a namespace")

        # Let's fork to become pid 1
        logging.debug("forking to become pid 1")
        child_pid = os.fork()
        if child_pid:
            logging.debug(
                "in parent pid %s waiting on child pid %s to exit", pid, child_pid
            )
            status = os.wait()
            logging.debug("parent %s got chld exit status %s", os.getpid(), status)
            sys.exit(os.waitstatus_to_exitcode(status))

        logging.debug("in child as pid %s", os.getpid())
        # We must be pid 1 now.
        assert os.getpid() == 1
        child_pid = None

    if not exec_args:
        if not new_pg:
            logging.debug("no exec args, no new process group")
            # # if 0 == os.getpgid(0):
            # status = os.setpgid(0, 1)
            # logging.debug("os.setpgid(0, 1) == %s", status)
        else:
            logging.debug("no exec args, creating new process group")
            # No exec so we are the "child".
            new_process_group()
    else:
        logging.debug("forking to run: %s", exec_args)
        child_pid = os.fork()
        if child_pid == 0:
            exec_child(exec_args)
            # NOTREACHED

    while True:
        if child_pid != -1:
            logging.info("parent: waiting for child pid %s to exit", child_pid)
            waitpid("parent")
        else:
            logging.info("parent: waiting to reap zombies")
            time.sleep(100)


def main():
    #
    # Parse CLI args.
    #

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-P",
        "--no-proc-group",
        action="store_true",
        help="Set to inherit the process group",
    )
    ap.add_argument(
        "-v", dest="verbose", action="count", default=0, help="More -v's, more verbose"
    )
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    #
    # Setup logging.
    #

    level = logging.DEBUG if args.verbose else logging.INFO
    if args.verbose > 1:
        global very_verbose  # pylint: disable=global-statement
        very_verbose = True
    logging.basicConfig(
        level=level, format="%(asctime)s mutini: %(levelname)s: %(message)s"
    )

    #
    # Run program
    #

    status = 4
    try:
        run(not args.no_proc_group, args.rest)
    except KeyboardInterrupt:
        logging.info("exiting (main), received KeyboardInterrupt in main")
    except Exception as error:
        logging.info("exiting (main), unexpected exception %s", error, exc_info=True)

    sys.exit(status)


if __name__ == "__main__":
    main()

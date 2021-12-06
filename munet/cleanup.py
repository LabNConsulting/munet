# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# September 30 2021, Christian Hopps <chopps@labn.net>
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
import glob
import logging
import os
import signal
import time


def get_pids_with_env(has_var, has_val=None):
    result = {}
    for pidenv in glob.iglob("/proc/*/environ"):
        pid = pidenv.split("/")[2]
        try:
            with open(pidenv, "rb") as rfb:
                envlist = [
                    x.decode("utf-8").split("=", 1) for x in rfb.read().split(b"\0")
                ]
                envlist = [[x[0], ""] if len(x) == 1 else x for x in envlist]
                envdict = dict(envlist)
                if has_var not in envdict:
                    continue
                if has_val is None:
                    result[pid] = envdict
                elif envdict[has_var] == str(has_val):
                    result[pid] = envdict
        except Exception:
            # E.g., process exited and files are gone
            pass
    return result


def _kill_piddict(pids_by_upid, sig):
    ourpid = str(os.getpid())
    for upid, pids in pids_by_upid:
        logging.info("Sending %s to (%s) of munet pid %s", sig, ", ".join(pids), upid)
        for pid in pids:
            try:
                if pid != ourpid:
                    cmdline = open(f"/proc/{pid}/cmdline", "r", encoding="ascii").read()
                    cmdline = cmdline.replace("\x00", " ")
                    logging.info("killing proc %s (%s)", pid, cmdline)
                    os.kill(int(pid), sig)
            except Exception:
                pass


def _get_our_pids():
    ourpid = str(os.getpid())
    piddict = get_pids_with_env("MUNET_PID", ourpid)
    pids = [x for x in piddict if x != ourpid]
    if pids:
        return {ourpid: pids}
    return {}


def _get_other_pids():
    piddict = get_pids_with_env("MUNET_PID")
    unet_pids = {d["MUNET_PID"] for d in piddict.values()}
    pids_by_upid = {p: set() for p in unet_pids}
    for pid, envdict in piddict.items():
        unet_pid = envdict["MUNET_PID"]
        pids_by_upid[unet_pid].add(pid)
    # Filter out any child pid sets whos munet pid is still running
    return {x: y for x, y in pids_by_upid.items() if x not in y}


def _get_pids_by_upid(ours):
    if ours:
        return _get_our_pids()
    return _get_other_pids()


def _cleanup_pids(ours):
    pids_by_upid = _get_pids_by_upid(ours).items()
    if not pids_by_upid:
        return

    t = "current" if ours else "previous"
    logging.info("Reaping %s  munet processes", t)

    _kill_piddict(pids_by_upid, signal.SIGTERM)

    # Give them 5 second to exit cleanly
    logging.info("Waiting up to 5s to allow for clean exit of abandon'd pids")
    for _ in range(0, 5):
        pids_by_upid = _get_pids_by_upid(ours).items()
        if not pids_by_upid:
            return
        time.sleep(1)

    pids_by_upid = _get_pids_by_upid(ours).items()
    _kill_piddict(pids_by_upid, signal.SIGKILL)


def cleanup_current():
    """Attempt to cleanup preview runs.

    Currently this only scans for old processes.
    """
    _cleanup_pids(True)


def cleanup_previous():
    """Attempt to cleanup preview runs.

    Currently this only scans for old processes.
    """
    _cleanup_pids(False)

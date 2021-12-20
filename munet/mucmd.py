# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 5 2021, Christian Hopps <chopps@labn.net>
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
import json
import os
import sys


def main(*args):
    ap = argparse.ArgumentParser(args)
    ap.add_argument("-d", "--rundir", help="runtime directory for tempfiles, logs, etc")
    ap.add_argument("node", nargs="?", help="node to enter or run command inside")
    ap.add_argument(
        "shellcmd",
        nargs=argparse.REMAINDER,
        help="optional shell-command to execute on NODE",
    )
    args = ap.parse_args()
    rundir = args.rundir if args.rundir else "/tmp/unet-" + os.environ["USER"]
    if not os.path.exists(rundir):
        print(f'rundir "{rundir}" doesn\'t exist')
        return 1

    nodes = []
    config = json.load(open(os.path.join(rundir, "config.json"), encoding="utf-8"))
    nodes = list(config.get("topology", {}).get("nodes", []))
    envcfg = config.get("mucmd", {}).get("env", {})

    # If args.node is not a node it's part of shellcmd
    if args.node and args.node not in nodes:
        args.shellcmd[0:0] = [args.node]
        args.node = None

    if args.node:
        name = args.node
        pidpath = os.path.join(rundir, f"{args.node}/nspid")
    else:
        name = "munet"
        pidpath = os.path.join(rundir, "nspid")
    pid = open(pidpath, encoding="ascii").read().strip()

    env = {**os.environ}
    env["MUNET_NODENAME"] = name
    env["MUNET_RUNDIR"] = rundir

    for k in envcfg:
        envcfg[k] = envcfg[k].replace("%NAME%", name)
        envcfg[k] = envcfg[k].replace("%RUNDIR%", rundir)

    ecmd = "/usr/bin/nsenter"
    eargs = [ecmd, "-aF", "-t", pid] + args.shellcmd
    return os.execvpe(ecmd, eargs, {**env, **envcfg})


if __name__ == "__main__":
    exit_status = main()
    sys.exit(exit_status)

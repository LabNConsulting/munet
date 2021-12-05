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

import os
import argparse
import json
import subprocess


def main(*args):
    ap = argparse.ArgumentParser(args)
    ap.add_argument(
        "-i", "--instance", default="0", help="instance (allows for parallel runs)"
    )
    ap.add_argument("-d", "--rundir", help="runtime directory for tempfiles, logs, etc")
    ap.add_argument("node", nargs="?", help="node to enter or run command inside")
    ap.add_argument(
        "shellcmd",
        nargs=argparse.REMAINDER,
        help="optional shell-command to execute on NODE",
    )

    args = ap.parse_args()

    rundir = args.rundir if args.rundir else f"/tmp/unet-{args.instance}"

    if not os.path.exists(rundir):
        print(f'rundir "{rundir}" doesn\'t exist')
        return 1

    config = json.load(open(os.path.join(rundir, "config.json"), encoding="utf-8"))

    if not args.node:
        pidpath = os.path.join(rundir, "nspid")
    else:
        pidpath = os.path.join(rundir, f"{args.node}/nspid")
    pid = open(pidpath, encoding="ascii").read().strip()

    return os.execvp("sudo", ["sudo", "nsenter", "-aF", "-t", pid] + args.shellcmd)
    return 0


if __name__ == "__main__":
    exit_status = main()
    sys.exit(exit_status)

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# June 10 2022, Christian Hopps <chopps@labn.net>
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
"""A module that gives access to linux unshare system call."""

import ctypes  # pylint: disable=C0415
import ctypes.util  # pylint: disable=C0415

libc = None


def unshare(flags):
    global libc  # pylint: disable=W0601,W0603
    if libc is None:
        lcpath = ctypes.util.find_library("c")
        libc = ctypes.CDLL(lcpath, use_errno=True)
    if libc.unshare(flags) == -1:
        raise OSError(ctypes.get_errno())


CLONE_NEWTIME = 0x00000080
CLONE_VM = 0x00000100
CLONE_FS = 0x00000200
CLONE_FILES = 0x00000400
CLONE_SIGHAND = 0x00000800
CLONE_PIDFD = 0x00001000
CLONE_PTRACE = 0x00002000
CLONE_VFORK = 0x00004000
CLONE_PARENT = 0x00008000
CLONE_THREAD = 0x00010000
CLONE_NEWNS = 0x00020000
CLONE_SYSVSEM = 0x00040000
CLONE_SETTLS = 0x00080000
CLONE_PARENT_SETTID = 0x00100000
CLONE_CHILD_CLEARTID = 0x00200000
CLONE_DETACHED = 0x00400000
CLONE_UNTRACED = 0x00800000
CLONE_CHILD_SETTID = 0x01000000
CLONE_NEWCGROUP = 0x02000000
CLONE_NEWUTS = 0x04000000
CLONE_NEWIPC = 0x08000000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
CLONE_IO = 0x80000000

clone_flag_names = {
    CLONE_NEWTIME: "CLONE_NEWTIME",
    CLONE_VM: "CLONE_VM",
    CLONE_FS: "CLONE_FS",
    CLONE_FILES: "CLONE_FILES",
    CLONE_SIGHAND: "CLONE_SIGHAND",
    CLONE_PIDFD: "CLONE_PIDFD",
    CLONE_PTRACE: "CLONE_PTRACE",
    CLONE_VFORK: "CLONE_VFORK",
    CLONE_PARENT: "CLONE_PARENT",
    CLONE_THREAD: "CLONE_THREAD",
    CLONE_NEWNS: "CLONE_NEWNS",
    CLONE_SYSVSEM: "CLONE_SYSVSEM",
    CLONE_SETTLS: "CLONE_SETTLS",
    CLONE_PARENT_SETTID: "CLONE_PARENT_SETTID",
    CLONE_CHILD_CLEARTID: "CLONE_CHILD_CLEARTID",
    CLONE_DETACHED: "CLONE_DETACHED",
    CLONE_UNTRACED: "CLONE_UNTRACED",
    CLONE_CHILD_SETTID: "CLONE_CHILD_SETTID",
    CLONE_NEWCGROUP: "CLONE_NEWCGROUP",
    CLONE_NEWUTS: "CLONE_NEWUTS",
    CLONE_NEWIPC: "CLONE_NEWIPC",
    CLONE_NEWUSER: "CLONE_NEWUSER",
    CLONE_NEWPID: "CLONE_NEWPID",
    CLONE_NEWNET: "CLONE_NEWNET",
    CLONE_IO: "CLONE_IO",
}

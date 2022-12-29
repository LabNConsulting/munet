# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 28 2022, Christian Hopps <chopps@labn.net>
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
"""Test mutest execution.

This test is for testing various CLI options and console output of mutest.
"""
from munet.mutest.userapi import match_step
from munet.mutest.userapi import script_dir
from munet.mutest.userapi import section


section("Test running mutest executable")

sd = script_dir()
match_step(
    "host1",
    f"cd {sd} && mutest --help",
    "positional arguments:.*\n.*paths",
    "Check help",
)
match_step(
    "host1",
    f"cd {sd} && mutest -d /tmp/mutest2/ --file-select='mut_*'",
    "FAIL",
    "Verify FAIL case",
)

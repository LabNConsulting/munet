# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 19 2022, Christian Hopps <chopps@labn.net>
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
"""Test command execution.

This test is for testing various command functionality to make sure that
complex commands to targets work.
"""
from munet.mutest.userapi import match_step
from munet.mutest.userapi import script_dir
from munet.mutest.userapi import test
from munet.mutest.userapi import wait_step


for search_string in [
    r"(.*Full){2,}",
    # r"((.|\s)*Full){2,}", This is so slow it looks like a hang
]:
    success, match = wait_step(
        target="r1",
        cmd=f"cat {script_dir()}/show_output.txt",
        match=search_string,
        timeout=1,
        desc=f'Verify counting "Full" adjacencies with regexp: "{search_string}"',
    )
    test(success is True, desc="Verify success value is True")

for search_string in [
    r"(.*Full){3,}",
    # r"((.|\s)*Full){2,}", This is so slow it looks like a hang
]:
    success, match = wait_step(
        target="r1",
        cmd=f"cat {script_dir()}/show_output.txt",
        match=search_string,
        timeout=1,
        desc=f'Verify counting "Full" adjacencies with regexp: "{search_string}"',
        expect_fail=True,
    )
    test(success is True, desc="Verify success value is True")

success, match = match_step(
    target="r1", cmd="ls -l / | grep dev", match="dev", desc="Verify shell pipe works"
)
test(success is True, desc="Verify success value is True")

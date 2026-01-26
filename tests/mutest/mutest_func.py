# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# December 19 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"""Test command execution.

This test is for testing various command functionality to make sure that
complex commands to targets work.
"""

from munet.mutest.userapi import match_step
from munet.mutest.userapi import script_dir
from munet.mutest.userapi import test_step
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
    test_step(success is True, desc="Verify success value is True")

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
    test_step(success is True, desc="Verify success value is True")

success, match = match_step(
    target="r1", cmd="ls -l / | grep dev", match="dev", desc="Verify shell pipe works"
)
test_step(success is True, desc="Verify success value is True")

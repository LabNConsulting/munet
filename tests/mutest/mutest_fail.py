# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# December 28 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
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
    f"cd {sd} && mutest -d $MUNET_RUNDIR/failtest1 --file-select='mut_*'",
    "FAIL.*A failing test case",
    "Verify FAIL case",
)

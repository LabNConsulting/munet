# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# December 20 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"""Test section and include functionality."""

from munet.mutest.userapi import include
from munet.mutest.userapi import match_step
from munet.mutest.userapi import section
from munet.mutest.userapi import test_step

section("A section testing echo commands")
match_step("host1", "echo Hello", "Hello", "Test echo Hello")
match_step("host1", "echo World", "World", "Test echo World")

section("A section testing printf commands")
match_step("host1", 'printf "%s\n" "Hello"', "Hello", "Test printf with Hello arg")
match_step("host1", 'printf "%s\n" "World"', "World", "Test printf with World arg")

include("include/inc_subtest.py", True)
include("include/inc_withsection.py", True)

test_step(True, "Test after an 2 non-inline includes")
test_step(True, "A second test case with a target", "zoot")

section("A section with an inline include")
include("include/inc_subtest.py")

test_step(True, "A test after an inline include")

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# August 21 2025, Liam Brady <lbrady@labn.net>
#
# Copyright (c) 2025, LabN Consulting, L.L.C.
#
"""Test groups (First half of test).

This test is part of a pair written to ensure that mutests within the
same group are run within the same topology instance. This allows one
test to affect the running state for subsequent tests.
"""
from munet.mutest.userapi import step
from munet.mutest.userapi import match_step


step("r1", 'echo "bar" > foo.txt')

match_step("r1", 'cat foo.txt', r"bar", "Created a temporary file")

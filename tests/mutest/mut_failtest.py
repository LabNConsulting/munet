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

from munet.mutest.userapi import test_step

test_step(False, "A failing test case")

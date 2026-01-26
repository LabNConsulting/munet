# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# May 4 2024, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2024, LabN Consulting, L.L.C.
#
"""Test that bad json always fails.

This test should always fail so in a automation setup one must
run mutest nested in a mutest test and verify it fails.
"""

from munet.mutest.userapi import match_step_json

jsonblank = "{}"
jsonbad = '{"bad":"trailing-comma",}'

_, ret = match_step_json(
    "r1",
    f"echo '{jsonblank}'",
    jsonbad,
    "Output json is blank, match json is bad, always fail (even with expect fail)",
    expect_fail=True,
)

_, ret = match_step_json(
    "r1",
    f"echo '{jsonblank}'",
    jsonbad,
    "Output json is blank, match json is bad, always fail",
    expect_fail=False,
)

_, ret = match_step_json(
    "r1",
    f"echo '{jsonbad}'",
    jsonblank,
    "Output json is bad, match json is blank, always fail (even with expect fail)",
    expect_fail=True,
)

_, ret = match_step_json(
    "r1",
    f"echo '{jsonbad}'",
    jsonblank,
    "Output json is bad, match json is blank, always fail",
    expect_fail=False,
)

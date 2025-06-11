# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# April 18 2025, Liam Brady <lbrady@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"""Test for config of env variables.

This test is for ensuring that configured environment variables properly appear
within run commands.
"""
import munet
from munet.mutest.userapi import match_step
from munet.mutest.userapi import section

# Configured environment variables also should be set within
# new munet windows, however, this is not tested here.

section("Test config for env variables")

match_step(
    "r1",
    "cat cmd.out",
    "bar",
    "Check for env variable in cmd.out",
    exact_match=True,
)
match_step(
    "r1",
    "echo $foo0",
    "bar",
    "Check for env variable in Linux namespace",
    exact_match=True,
)
match_step(
    "r1",
    "echo $foo1",
    "bar '\" baz",
    "Check env variable for proper quoting",
    exact_match=True,
)

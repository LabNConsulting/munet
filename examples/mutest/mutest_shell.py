# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# April 12 2024, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2024, LabN Consulting, L.L.C.
"""Example mutest."""

from munet.mutest.userapi import match_step
from munet.mutest.userapi import section
from munet.mutest.userapi import step
from munet.mutest.userapi import wait_step

section("Tests to show use of steps.")

match_step(
    "h1",
    "ping -c1 10.0.1.2",
    match="0% packet loss",
    desc="h1 pings h2",
)

step("h1", "(sleep 2 && touch foo) &")
wait_step(
    "h1",
    "ls",
    "foo",
    "found file foo",
)
step("h1", "rm -f foo")

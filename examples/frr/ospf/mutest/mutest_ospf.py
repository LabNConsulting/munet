# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# April 12 2024, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2024, LabN Consulting, L.L.C.
"""Example mutest."""

from munet.mutest.userapi import match_step
from munet.mutest.userapi import section
from munet.mutest.userapi import wait_step

section("Test to verify OSPF neighbors are up.")

wait_step(
    "r1",
    "vtysh -c 'show module'",
    match="ospfd daemon",
    desc="OSPF loaded",
)

match_step(
    "r1",
    "vtysh -c 'show run'",
    match="router ospf",
    desc="OSPF configured",
)

wait_step(
    "r1",
    "vtysh -c 'show ip ospf neigh'",
    match="(.*Full){2,}",
    timeout=15,
    desc="Verify 2 Full neighbors on router r1",
)

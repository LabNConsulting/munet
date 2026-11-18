# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 18 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"Testing of intf config limits"

import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_config_intf_limits(unet_share):
    unet = unet_share
    rn = unet.hosts["node-max-unlimited-char"]
    output = rn.cmd_raises("ip link")
    assert "itf-max-15-char" in output

    output = unet.cmd_raises("ip link")
    assert "net-max-15-char" in output
    assert "br1-e0" in output

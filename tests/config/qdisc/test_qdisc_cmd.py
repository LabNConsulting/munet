# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 28 2025, Liam Brady <lbrady@labn.net>
#
# Copyright 2025, LabN Consulting, L.L.C.
#
"Testing that qdiscs are properly set on network/node interfaces"
import logging
import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_config_cmd(unet_share):
    unet = unet_share

    output = unet.cmd_raises("tc q | grep 'dev net1-e0'")
    logging.debug("qdisc for dev net1-e0 output found: %s", output)
    logging.debug("expects delay='16', jitter='30', loss='40', rate='800'")
    assert "delay 16us" in output
    assert "loss 40" in output
    assert "29us" in output
    assert "rate 800bit" in output

    h1 = unet.hosts["h1"]
    output = h1.cmd_raises("tc q | grep 'dev eth0'")
    logging.debug("qdisc for dev eth0 output found: %s", output)
    logging.debug("expects delay='200', jitter='60', loss='70', rate='1600'")
    assert "delay 200us" in output
    assert "loss 70" in output
    assert "59us" in output
    assert "rate 1600bit" in output

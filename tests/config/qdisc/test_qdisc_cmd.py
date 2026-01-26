# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 28 2025, Liam Brady <lbrady@labn.net>
#
# Copyright 2025, LabN Consulting, L.L.C.
#
"Testing that qdiscs are properly set on network/node interfaces"

import logging
import re

import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_config_cmd(unet_share):
    unet = unet_share

    output = unet.cmd_raises("tc q | grep 'dev net1-e0'")
    logging.debug("qdisc for dev net1-e0 output found: %s", output)
    logging.debug("expects delay='16', jitter='30', loss='40', rate='800'")
    assert re.search(r"delay 16us\s+29us.*loss 40%.*rate 800bit", output, re.DOTALL)

    output = unet.cmd_raises("tc q | grep 'dev net1-e1'")
    logging.debug("qdisc for dev net1-e1 output found: %s", output)
    logging.debug("expects delay='6', jitter='20', loss='50', rate='810'")
    assert re.search(r"delay 17us\s+27us.*loss 38%.*rate 808bit", output, re.DOTALL)

    output = unet.cmd_raises("tc q | grep 'dev net1-e2'")
    logging.debug("qdisc for dev net1-e2 output found: %s", output)
    logging.debug("expects delay='13'")
    assert "delay 13us" in output
    assert "loss" not in output
    assert "rate" not in output

    h1 = unet.hosts["h1"]
    output = h1.cmd_raises("tc q | grep 'dev eth0'")
    logging.debug("qdisc for dev eth0 output found: %s", output)
    logging.debug("expects delay='200', jitter='60', loss='70', rate='1600'")
    assert re.search(r"delay 200us\s+59us.*loss 70%.*rate 1600bit", output, re.DOTALL)

    h2 = unet.hosts["h2"]
    output = h2.cmd_raises("tc q | grep 'dev eth0'")
    logging.debug("qdisc for dev eth0 output found: %s", output)
    logging.debug("expects delay='209', jitter='60', loss='70', rate='1600'")
    assert re.search(r"delay 209us\s+59us.*loss 70%.*rate 1600bit", output, re.DOTALL)

    h3 = unet.hosts["h3"]
    output = h3.cmd_raises("tc q | grep 'dev eth0'")
    logging.debug("qdisc for dev eth0 output found: %s", output)
    logging.debug("expects none")
    assert "delay" not in output
    assert "loss" not in output
    assert "rate" not in output

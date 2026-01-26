# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# June 28 2023, Eric Kinzie <ekinzie@labn.net>
#
# Copyright 2023, LabN Consulting, L.L.C.
#
"Test p2p peer addresses"

import logging
import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_peer_address(unet):
    rc, o, e = await unet.hosts["r1"].async_cmd_status(f"ip addr show dev eth0")
    assert rc == 0
    assert o.find("mtu 4500") > -1
    assert o.find("inet 172.16.0.1 peer 172.16.1.0/24") > -1
    assert o.find("inet6 2001:db8::1 peer 2001:db8::1:0/112") > -1

    rc, o, e = await unet.hosts["r2"].async_cmd_status(f"ip addr show dev eth0")
    assert rc == 0
    assert o.find("mtu 4500") > -1
    assert o.find("inet 172.16.1.2 peer 172.16.0.1/32") > -1
    assert o.find("inet6 2001:db8::1:1 peer 2001:db8::1/128") > -1


async def test_peer_ping(unet):
    r1eth0 = unet.hosts["r1"].get_intf_addr("eth0").ip
    logging.debug("r1eth0 is %s", r1eth0)
    o = await unet.hosts["r2"].async_cmd_raises(f"ping -w1 -c1 172.16.0.1")
    logging.debug("ping r2 output: %s", o)

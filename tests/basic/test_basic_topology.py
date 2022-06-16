# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; see the file COPYING; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
"Testing of basic topology configuration."
import logging

import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "unet_perfunc", ["munet", "noinit", "noinit-noshell"], indirect=["unet_perfunc"]
)
async def test_basic_ping(unet_perfunc):
    unet = unet_perfunc
    other_ip = unet.hosts["r2"].intf_addrs["eth0"].ip
    o = await unet.hosts["r1"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.info("ping r2 output: %s", o)


@pytest.mark.parametrize("unet_perfunc", ["munet"], indirect=["unet_perfunc"])
async def test_autonumber_ping(unet_perfunc):
    unet = unet_perfunc
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]

    for i in range(1, 4):
        logging.info(
            "r%s addrs: %s", i, await unet.hosts[f"r{i}"].async_cmd_raises("ip -o addr")
        )

    o = await r1.async_cmd_raises("ping -w1 -c1 10.0.1.2")
    logging.info("r1 ping r2 (10.0.1.2) output: %s", o)

    o = await r1.async_cmd_raises("ping -w1 -c1 192.168.10.3")
    logging.info("r1 ping r3 (192.168.10.3) output: %s", o)

    o = await r2.async_cmd_raises("ping -w1 -c1 10.254.1.0")
    logging.info("r2 ping r1 p2p (10.254.1.0) output: %s", o)

    o = await r2.async_cmd_raises("ping -w1 -c1 10.254.2.1")
    logging.info("r2 ping r3 p2p (10.254.2.1) output: %s", o)

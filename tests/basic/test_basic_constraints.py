# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# October 26 2021, Christian Hopps <chopps@labn.net>
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
import logging
import re

import pytest

from munet import Munet

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def ping_average_rtt(r, other, oifname):
    oip = other.intf_addrs[oifname].ip
    await r.async_cmd_raises(f"ping -w1 -c1 {oip}")
    o = await r.async_cmd_raises(f"ping -i.1 -c5 {oip}")
    m = re.search(r"min/avg/max/mdev = ([^/]+)/([^/]+)([^/]+)/([^ ]+) ms", o)
    return float(m.group(2))


async def ping_with_loss(r, other, oifname):
    oip = other.intf_addrs[oifname].ip
    await r.async_cmd_status(f"ping -w1 -c1 {oip}")
    r, o, e = await r.async_cmd_status(f"ping -i.01 -c300 {oip}")
    ms = r"(\d+) packets transmitted, (\d+) received"
    m = re.search(ms, o)
    sent, recv = [float(x) for x in m.groups()]
    return 100 - (100 * recv / sent)


async def test_basic_ping(rundir):
    unet = Munet(rundir)

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    r3 = unet.add_l3_node("r3")

    sw1 = unet.add_l3_switch("sw1")
    unet.add_l3_link(sw1, r1)
    unet.add_l3_link(sw1, r2)

    #
    # L3 API w/ delay constraint
    #
    ifname = "p2p0"
    ci1 = {"name": ifname, "delay": 80000}
    ci2 = {"name": ifname, "delay": 40000}
    exp_avg = (ci1["delay"] + ci2["delay"]) / 1000
    unet.add_l3_link(r2, r3, ci1, ci2)

    avg = await ping_average_rtt(r2, r3, ifname)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)

    #
    # Base API w/ delay constraint
    #
    ifname = "p2p1"
    c3 = {"name": ifname}
    unet.add_link(r2, r3, ifname, ifname, delay=200000)
    exp_avg = (200000 * 2) / 1000
    r2.set_p2p_addr(r3, c3, c3)

    avg = await ping_average_rtt(r2, r3, ifname)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)

    #
    # Base API w/ loss constraints
    #
    ifname = "p2p2"
    ci1 = {"name": ifname, "delay": 1, "loss": 30, "loss-correlation": 0}
    ci2 = {"name": ifname}
    unet.add_l3_link(r2, r3, ci1, ci2)

    loss = await ping_with_loss(r2, r3, ifname)
    logging.info("ping loss: %s%%", loss)
    assert 25 < loss < 35

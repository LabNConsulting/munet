# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 6 2026, Jafar Al-Gharaibeh <jafar@atcorp.com>
#
"Testing of interface constraints applied on the switch side of links."

import logging
import re

import pytest

from munet import Munet

# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="function", name="unet_case")
async def unet_case_(request, rundir, pytestconfig):
    """Per-test munet so switch/node names do not collide with other cases."""
    unshare = bool(request.param) if hasattr(request, "param") else True
    logging.info("Creating munet with%s inline unshare", "" if unshare else "out")
    unet = Munet(rundir=rundir, unshare_inline=unshare, pytestconfig=pytestconfig)
    try:
        yield unet
    finally:
        await unet.async_delete()


async def ping_average_rtt(r, other, oifname):
    oip = other.get_intf_addr(oifname).ip
    await r.async_cmd_raises(f"ping -w1 -c1 {oip}")
    o = await r.async_cmd_raises(f"ping -i.1 -c5 {oip}")
    m = re.search(r"min/avg/max/mdev = ([^/]+)/([^/]+)([^/]+)/([^ ]+) ms", o)
    return float(m.group(2))


@pytest.mark.parametrize("unet_case", [False, True], indirect=["unet_case"])
async def test_switch_constraints_outside_node(unet_case):
    """Node delay/rate stay TX-shaped, but the qdisc lives in the switch ns."""
    unet = unet_case
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    sw1 = unet.add_network("sw1", {"ip": "auto"})

    delay = 50000
    await unet.add_native_link(sw1, r1, {}, {"delay": delay})
    await unet.add_native_link(sw1, r2, {}, {"delay": delay})

    rif1 = r1.net_intfs[sw1.name]
    rif2 = r2.net_intfs[sw1.name]
    sif1 = sw1.intfs[0]
    sif2 = sw1.intfs[1]

    r1q = await r1.async_cmd_raises(f"tc qdisc show dev {rif1}")
    r2q = await r2.async_cmd_raises(f"tc qdisc show dev {rif2}")
    s1q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif1}")
    s2q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif2}")
    swq = await sw1.async_cmd_raises("tc qdisc show")
    logging.info("node qdiscs: %s | %s", r1q, r2q)
    logging.info("switch port qdiscs: %s | %s", s1q, s2q)
    logging.info("switch ns qdiscs: %s", swq)
    assert "netem" not in r1q
    assert "netem" not in r2q
    assert "ingress" in s1q
    assert "ingress" in s2q
    assert "netem" not in s1q
    assert "netem" not in s2q
    assert "netem" in swq

    exp_avg = (delay + delay) / 1000
    avg = await ping_average_rtt(r1, r2, rif2)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)

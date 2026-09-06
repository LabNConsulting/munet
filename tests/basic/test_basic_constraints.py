# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# October 26 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing of basic inteface constraints."

import logging
import re

import pytest

from munet import Munet
from munet.config import find_matching_net_config

# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module", name="unet")
async def unet_(request, rundir_module, pytestconfig):
    unshare = bool(request.param) if hasattr(request, "param") else True
    logging.info("Creating munet with%s inline unshare", "" if unshare else "out")
    unet = Munet(
        rundir=rundir_module, unshare_inline=unshare, pytestconfig=pytestconfig
    )
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


async def ping_with_loss(r, other, oifname):
    oip = other.get_intf_addr(oifname).ip
    await r.async_cmd_status(f"ping -w1 -c1 {oip}", warn=False)
    r, o, _ = await r.async_cmd_status(f"ping -i.001 -c500 {oip}")
    ms = r"(\d+) packets transmitted, (\d+) received"
    m = re.search(ms, o)
    sent, recv = [float(x) for x in m.groups()]
    return 100 - (100 * recv / sent)


@pytest.mark.parametrize("unet", [False, True], indirect=["unet"])
async def test_basic_ping(unet):
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    r3 = unet.add_l3_node("r3")

    sw1 = unet.add_network("sw1", {"ip": "auto"})
    await unet.add_native_link(sw1, r1)
    await unet.add_native_link(sw1, r2)

    #
    # L3 API w/ delay constraint
    #
    ifname = "p2p0"
    ci1 = {"name": ifname, "delay": 80000}
    ci2 = {"name": ifname, "delay": 40000}
    exp_avg = (ci1["delay"] + ci2["delay"]) / 1000
    await unet.add_native_link(r2, r3, ci1, ci2)

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
    # ci1 = {"name": ifname, "delay": 1, "loss": 30, "loss-correlation": 0}
    ci1 = {"name": ifname, "loss": 30}
    ci2 = {"name": ifname}
    await unet.add_native_link(r2, r3, ci1, ci2)

    loss = await ping_with_loss(r2, r3, ifname)
    logging.info("ping loss: %s%%", loss)
    assert 20 < loss < 40


@pytest.mark.parametrize("unet", [False, True], indirect=["unet"])
async def test_switch_constraints_outside_node(unet):
    """Node delay/rate stay TX-shaped, but the qdisc lives in the switch ns."""
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


@pytest.mark.parametrize("unet", [False, True], indirect=["unet"])
async def test_switch_to_and_from(unet):
    """Switch to: is node RX; from: is node TX (IFB). Together they are RTT."""
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    sw1 = unet.add_network("sw1", {"ip": "auto"})

    delay = 50000
    await unet.add_native_link(
        sw1, r1, {"delay": delay}, {}, c1_from={"delay": delay}
    )
    await unet.add_native_link(
        sw1, r2, {"delay": delay}, {}, c1_from={"delay": delay}
    )

    rif2 = r2.net_intfs[sw1.name]
    sif1 = sw1.intfs[0]
    sif2 = sw1.intfs[1]
    r1q = await r1.async_cmd_raises(
        f"tc qdisc show dev {r1.net_intfs[sw1.name]}"
    )
    s1q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif1}")
    s2q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif2}")
    swq = await sw1.async_cmd_raises("tc qdisc show")
    logging.info("node qdisc: %s", r1q)
    logging.info("switch ports: %s | %s", s1q, s2q)
    logging.info("switch ns: %s", swq)
    assert "netem" not in r1q
    assert "ingress" in s1q and "netem" in s1q
    assert "ingress" in s2q and "netem" in s2q
    assert "ifb" in swq

    # TX + RX on each hop: 4 * 50ms
    exp_avg = (delay * 4) / 1000
    avg = await ping_average_rtt(r1, r2, rif2)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)


def test_find_matching_net_to_from():
    """Switch connections match separately on to: and from:."""
    sw = {
        "connections": [
            {"to": "r1", "delay": 1000, "rate": {"rate": "15M"}},
            {"from": "r1", "delay": 2000, "rate": {"rate": "30M"}},
            {"to": "r2", "delay": 3000},
        ]
    }
    cconf = {"name": "eth0"}
    toward = find_matching_net_config("r1", cconf, sw, "to")
    leaving = find_matching_net_config("r1", cconf, sw, "from")
    assert toward["delay"] == 1000
    assert toward["rate"]["rate"] == "15M"
    assert leaving["delay"] == 2000
    assert leaving["rate"]["rate"] == "30M"
    assert find_matching_net_config("r2", cconf, sw, "from") == {}
    assert find_matching_net_config("r3", cconf, sw, "to") == {}
    assert Munet._tc_constraints(None) == {}
    tx = Munet._tc_constraints(leaving)
    rx = Munet._tc_constraints(toward)
    assert tx["delay"] == 2000
    assert rx["delay"] == 1000
    assert "name" not in tx
    # Node delay overrides switch from: on the same TX pipe.
    assert Munet._tc_constraints(leaving, {"delay": 100})["delay"] == 100


@pytest.mark.parametrize("unet", [False, True], indirect=["unet"])
async def test_switch_to_delay_only(unet):
    """Switch to: shapes RX on switch egress (no IFB)."""
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    sw1 = unet.add_network("sw1", {"ip": "auto"})

    delay = 50000
    await unet.add_native_link(sw1, r1, {"delay": delay}, {})
    await unet.add_native_link(sw1, r2, {"delay": delay}, {})

    rif2 = r2.net_intfs[sw1.name]
    sif1 = sw1.intfs[0]
    sif2 = sw1.intfs[1]
    r1q = await r1.async_cmd_raises(f"tc qdisc show dev {r1.net_intfs[sw1.name]}")
    s1q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif1}")
    s2q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif2}")
    swq = await sw1.async_cmd_raises("tc qdisc show")
    logging.info("node qdisc: %s", r1q)
    logging.info("switch ports: %s | %s", s1q, s2q)
    logging.info("switch ns: %s", swq)
    assert "netem" not in r1q
    assert "ingress" not in s1q and "netem" in s1q
    assert "ingress" not in s2q and "netem" in s2q
    assert "ifb" not in swq

    exp_avg = (delay + delay) / 1000
    avg = await ping_average_rtt(r1, r2, rif2)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)

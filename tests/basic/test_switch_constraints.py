# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 6 2026, Jafar Al-Gharaibeh <jafar@atcorp.com>
#
"Testing of interface constraints applied on the switch side of links."

import logging
import re
from copy import deepcopy

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


@pytest.mark.parametrize("unet_case", [False, True], indirect=["unet_case"])
async def test_switch_transmit_and_receive(unet_case):
    """Switch transmit is node RX; receive is node TX (IFB). Together RTT."""
    unet = unet_case
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    sw1 = unet.add_network("sw1", {"ip": "auto"})

    delay = 50000
    swc = {"transmit": {"delay": delay}, "receive": {"delay": delay}}
    await unet.add_native_link(sw1, r1, dict(swc), {})
    await unet.add_native_link(sw1, r2, dict(swc), {})

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
    assert "ingress" in s1q and "netem" in s1q
    assert "ingress" in s2q and "netem" in s2q
    assert "ifb" in swq

    # TX + RX on each hop: 4 * 50ms
    exp_avg = (delay * 4) / 1000
    avg = await ping_average_rtt(r1, r2, rif2)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)


def test_tc_directions():
    """Unwrapped keys are transmit; containers override and split direction."""
    # pylint: disable=protected-access
    assert not Munet._tc_transmit(None)
    assert not Munet._tc_receive(None)
    assert not Munet._tc_receive({"delay": 1000})

    conf = {
        "name": "eth0",
        "delay": 1000,
        "loss": 5,
        "transmit": {"delay": 2000, "rate": {"rate": "15M"}},
        "receive": {"delay": 3000},
    }
    tx = Munet._tc_transmit(conf)
    rx = Munet._tc_receive(conf)
    assert tx == {"delay": 2000, "loss": 5, "rate": {"rate": "15M"}}
    assert rx == {"delay": 3000}
    assert Munet._tc_transmit({"delay": 1000}) == {"delay": 1000}

    assert not Munet._tc_peers(None)
    assert not Munet._tc_peers(conf)
    peers = Munet._tc_peers(
        {"transmit": {"peers": [{"peer": "r1", "delay": 10, "name": "x"}]}}
    )
    assert peers == {"r1": {"delay": 10}}
    assert "peers" not in Munet._tc_transmit({"transmit": {"peers": []}})


@pytest.mark.parametrize("unet_case", [False, True], indirect=["unet_case"])
async def test_switch_transmit_peers(unet_case):
    """Per-peer transmit shapes only that peer's traffic toward the node."""
    unet = unet_case
    unet.autonumber = True

    peer_delay = 50000
    default_delay = 10000
    r2conn = {
        "to": "r2",
        "transmit": {
            "delay": default_delay,
            "peers": [{"peer": "r1", "delay": peer_delay}],
        },
    }
    sw1 = unet.add_network("sw1", {"ip": "auto", "connections": [r2conn]})
    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    r3 = unet.add_l3_node("r3")

    # Link r2 before its peer r1 so marks do not depend on link order.
    await unet.add_native_link(sw1, r2, deepcopy(r2conn), {})
    await unet.add_native_link(sw1, r1, {}, {})
    await unet.add_native_link(sw1, r3, {}, {})

    s2q = await sw1.async_cmd_raises(f"tc qdisc show dev {sw1.intfs[0]}")
    logging.info("r2 switch port qdiscs: %s", s2q)
    assert "drr" in s2q
    r2q = await r2.async_cmd_raises(f"tc qdisc show dev {r2.net_intfs[sw1.name]}")
    assert "netem" not in r2q

    # One way delays: r1 -> r2 peer_delay, r3 -> r2 default_delay, rest none.
    avg = await ping_average_rtt(r1, r2, r2.net_intfs[sw1.name])
    logging.info("r1 <-> r2 RTT: %s", avg)
    assert (peer_delay / 1000 - 1) < avg < (peer_delay / 1000 + 2)

    avg = await ping_average_rtt(r3, r2, r2.net_intfs[sw1.name])
    logging.info("r3 <-> r2 RTT: %s", avg)
    assert (default_delay / 1000 - 1) < avg < (default_delay / 1000 + 2)

    avg = await ping_average_rtt(r1, r3, r3.net_intfs[sw1.name])
    logging.info("r1 <-> r3 RTT: %s", avg)
    assert avg < 2


@pytest.mark.parametrize("unet_case", [False, True], indirect=["unet_case"])
async def test_switch_legacy_transmit_only(unet_case):
    """Deprecated unwrapped switch TC is transmit: switch egress (no IFB)."""
    unet = unet_case
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


@pytest.mark.parametrize("unet_case", [False, True], indirect=["unet_case"])
async def test_switch_node_receive(unet_case):
    """Node receive on a network link shapes switch egress, not the node."""
    unet = unet_case
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")
    sw1 = unet.add_network("sw1", {"ip": "auto"})

    delay = 50000
    await unet.add_native_link(sw1, r1, {}, {"receive": {"delay": delay}})
    await unet.add_native_link(sw1, r2, {}, {"receive": {"delay": delay}})

    rif2 = r2.net_intfs[sw1.name]
    sif1 = sw1.intfs[0]
    r1q = await r1.async_cmd_raises(f"tc qdisc show dev {r1.net_intfs[sw1.name]}")
    s1q = await sw1.async_cmd_raises(f"tc qdisc show dev {sif1}")
    swq = await sw1.async_cmd_raises("tc qdisc show")
    logging.info("node qdisc: %s", r1q)
    logging.info("switch port: %s", s1q)
    logging.info("switch ns: %s", swq)
    assert "netem" not in r1q
    assert "ingress" not in s1q and "netem" in s1q
    assert "ifb" not in swq

    exp_avg = (delay + delay) / 1000
    avg = await ping_average_rtt(r1, r2, rif2)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)


@pytest.mark.parametrize("unet_case", [False, True], indirect=["unet_case"])
async def test_p2p_receive(unet_case):
    """P2P receive is applied on the peer's egress."""
    unet = unet_case
    unet.autonumber = True

    r1 = unet.add_l3_node("r1")
    r2 = unet.add_l3_node("r2")

    ifname = "p2p0"
    delay = 50000
    c1 = {"name": ifname, "receive": {"delay": delay}}
    c2 = {"name": ifname}
    await unet.add_native_link(r1, r2, c1, c2)

    r1q = await r1.async_cmd_raises(f"tc qdisc show dev {ifname}")
    r2q = await r2.async_cmd_raises(f"tc qdisc show dev {ifname}")
    logging.info("node qdiscs: %s | %s", r1q, r2q)
    assert "netem" not in r1q
    assert "netem" in r2q

    exp_avg = delay / 1000
    avg = await ping_average_rtt(r1, r2, ifname)
    logging.info("ping average RTT: %s", avg)
    assert (exp_avg - 1) < avg < (exp_avg + 2)

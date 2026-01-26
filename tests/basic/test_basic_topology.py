# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing of basic topology configuration."

import logging

import pytest

from munet.base import cmd_error

# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "unet_perfunc", ["munet", "noinit", "noinit-noshell"], indirect=["unet_perfunc"]
)
async def test_basic_ping(unet_perfunc):
    unet = unet_perfunc
    other_ip = unet.hosts["r2"].get_intf_addr("eth0").ip
    o = await unet.hosts["r1"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.debug("ping r2 output: %s", o)


async def test_autonumber_ping(unet_perfunc):
    unet = unet_perfunc
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]

    for i in range(1, 4):
        logging.debug(
            "r%s addrs: %s", i, await unet.hosts[f"r{i}"].async_cmd_raises("ip -o addr")
        )

    o = await r1.async_cmd_raises("ping -w1 -c1 10.0.1.2")
    logging.debug("r1 ping r2 (10.0.1.2) output: %s", o)

    o = await r1.async_cmd_raises("ping -w1 -c1 192.168.10.3")
    logging.debug("r1 ping r3 (192.168.10.3) output: %s", o)

    o = await r2.async_cmd_raises("ping -w1 -c1 10.254.1.0")
    logging.debug("r2 ping r1 p2p (10.254.1.0) output: %s", o)

    o = await r2.async_cmd_raises("ping -w1 -c1 10.254.2.1")
    logging.debug("r2 ping r3 p2p (10.254.2.1) output: %s", o)

    o = await r2.async_cmd_raises("ping -w1 -c1 10.255.0.2")
    logging.debug("r2 ping lo (10.255.0.2) output: %s", o)

    if unet.ipv6_enable:
        addr = "fc00:0:0:1::2"
        o = await r1.async_cmd_nostatus("ip -6 neigh show dev xyz0")
        logging.info("ip -6 neigh show: %s", o)

        await r1.async_cmd_nostatus(f"ping -w5 -c3 {addr}", warn=False)

        o = await r1.async_cmd_nostatus(f"ip -6 neigh get {addr} dev xyz0")
        logging.info("ip -6 neigh get: %s", o)

        o = await r1.async_cmd_nostatus("ip -6 neigh show")
        logging.info("ip -6 neigh show: %s", o)

        o = await r1.async_cmd_raises(f"ping -w1 -c1 {addr}")
        logging.debug(f"r1 ping r2 ({addr}) output: %s", o)

        o = await r1.async_cmd_raises("ping -w1 -c1 fd00:10::3")
        logging.debug("r1 ping r3 (192.168.10.3) output: %s", o)

        o = await r2.async_cmd_raises("ping -w1 -c1 fcff:ffff:1::0")
        logging.debug("r2 ping r1 p2p (fcff:ffff:1::0) output: %s", o)

        o = await r2.async_cmd_raises("ping -w1 -c1 fcff:ffff:2::1")
        logging.debug("r2 ping r3 p2p (fcff:ffff:2::1) output: %s", o)

        o = await r2.async_cmd_raises("ping -w1 -c1 fcfe::2")
        logging.debug("r2 ping lo (fcfe::2) output: %s", o)

        o = await r1.async_cmd_nostatus("ip -6 neigh show")
        logging.info("ip -6 neigh show: %s", o)


@pytest.mark.parametrize("unet_perfunc", ["munet"], indirect=["unet_perfunc"])
async def test_basic_config(unet_perfunc):
    unet = unet_perfunc
    r3 = unet.hosts["r3"]

    o = await r3.async_cmd_raises("ping -w1 -c1 172.16.0.3")
    logging.debug("r3 ping lo (172.16.0.3) output: %s", o)

    o = await r3.async_cmd_raises("ping -w1 -c1 172.16.0.33")
    logging.debug("r3 ping lo (172.16.0.33) output: %s", o)

    o = await r3.async_cmd_raises("ping -w1 -c1 fe8f:ffff:3::1")
    logging.debug("r3 ping lo (fe8f:ffff:3::1) output: %s", o)

    o = await r3.async_cmd_raises("ping -w1 -c1 fe8f:ffff:33::1")
    logging.debug("r3 ping lo (fe8f:ffff:33::1) output: %s", o)


@pytest.mark.parametrize("ipv6", [False, True])
@pytest.mark.parametrize("unet_perfunc", [False, True], indirect=["unet_perfunc"])
async def test_mtu_ping(unet_perfunc, astepf, ipv6):
    unet = unet_perfunc
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]
    r3 = unet.hosts["r3"]

    logf = logging.debug

    dest = r2.get_intf_addr(r2.net_intfs["net0"], ipv6=ipv6).ip
    await astepf(f"ping r1 (4452) --- [net0:4500] ---> {dest} r2")
    # Need neighbor discovery to finish
    await r1.async_cmd_nostatus(f"ping -w5 -c3 -Mdo -s4452 {dest}", warn=False)

    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s4452 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r1 (4500) -X- [net0:4500] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s4500 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r3.get_intf_addr(r3.net_intfs["net1"], ipv6=ipv6).ip
    await astepf(f"ping r1 (8952) --- [net1:9000] ---> {dest} r3")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s8952 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r1 (9000) -X- [net1:9000] ---> {dest} r3")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s9000 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r2.get_intf_addr("p2p0", ipv6=ipv6).ip
    await astepf(f"ping r1 (8952) --- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s8952 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r1 (9000) -X- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s9000 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r2.get_intf_addr("p2p1", ipv6=ipv6).ip
    await astepf(f"ping r3 (1452) --- [p2p:1500] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s1452 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r3 (1500) -X- [p2p:1500] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s1500 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r2.get_intf_addr("p2p2", ipv6=ipv6).ip
    await astepf(f"ping r3 (8952) --- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s8952 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r3 (9000) -X- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s9000 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

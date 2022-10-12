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

from munet.base import cmd_error


# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "unet_perfunc", ["munet", "noinit", "noinit-noshell"], indirect=["unet_perfunc"]
)
async def test_basic_ping(unet_perfunc):
    unet = unet_perfunc
    other_ip = unet.hosts["r2"].intf_addrs["eth0"].ip
    o = await unet.hosts["r1"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.debug("ping r2 output: %s", o)


@pytest.mark.parametrize("unet_perfunc", ["munet"], indirect=["unet_perfunc"])
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


@pytest.mark.parametrize("unet_perfunc", ["munet"], indirect=["unet_perfunc"])
async def test_mtu_ping(unet_perfunc, astepf):
    unet = unet_perfunc
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]
    r3 = unet.hosts["r3"]

    logf = logging.debug

    dest = r2.intf_addrs[r2.net_intfs["net0"]].ip
    await astepf(f"ping r1 (4472) --- [net0:4500] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s4472 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r1 (4500) -X- [net0:4500] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s4500 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r3.intf_addrs[r3.net_intfs["net1"]].ip
    await astepf(f"ping r1 (8972) --- [net1:9000] ---> {dest} r3")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s8972 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r1 (9000) -X- [net1:9000] ---> {dest} r3")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s9000 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r2.intf_addrs["p2p0"].ip
    await astepf(f"ping r1 (8972) --- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s8972 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r1 (9000) -X- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r1.async_cmd_status(f"ping -w1 -c1 -Mdo -s9000 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r2.intf_addrs["p2p1"].ip
    await astepf(f"ping r3 (1472) --- [p2p:1500] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s1472 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r3 (1500) -X- [p2p:1500] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s1500 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

    dest = r2.intf_addrs["p2p2"].ip
    await astepf(f"ping r3 (8972) --- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s8972 {dest}")
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc == 0

    await astepf(f"ping r3 (9000) -X- [p2p:9000] ---> {dest} r2")
    rc, o, e = await r3.async_cmd_status(f"ping -w1 -c1 -Mdo -s9000 {dest}", warn=False)
    logf("ping: %s", cmd_error(rc, o, e))
    assert rc != 0

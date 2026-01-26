# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 13 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
#
"Tests of L3Qemu node type"

import logging

import pytest

# All tests are coroutines
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize("unet", ["munet-cloud"], indirect=["unet"]),
]


async def test_qemu_up(unet):
    r1 = unet.hosts["r1"]
    output = r1.monrepl.cmd_nostatus("info status")
    assert output == "VM status: running"


async def test_net_up(unet):
    h1 = unet.hosts["h1"]

    r_names = sorted([x for x in unet.hosts if x.startswith("r")])
    # eth1 => r1, eth2 => r2 ...
    hr_intf_names = [f"eth{name[1:]}" for name in r_names]

    rs = [unet.hosts[x] for x in r_names]

    h1mgmt0ip = h1.get_intf_addr("eth0").ip
    rs_mgmtips = [x.get_intf_addr("eth0").ip for x in rs]

    h1_r1ips = [h1.get_intf_addr(x).ip for x in hr_intf_names]
    rs_h1ips = [x.get_intf_addr("eth1").ip for x in rs]

    logging.debug(h1.cmd_raises("ping -w1 -c1 192.168.0.254"))
    for ip in rs_mgmtips:
        logging.debug(h1.cmd_raises(f"ping -w1 -c1 {ip}"))
    for ip in rs_h1ips:
        logging.debug(h1.cmd_raises(f"ping -w1 -c1 {ip}"))

    # Will use Console.
    for r, h1ip in zip(rs, h1_r1ips):
        logging.debug(r.conrepl.cmd_raises("ping -w1 -c1 192.168.0.254"))
        logging.debug(r.conrepl.cmd_raises(f"ping -w1 -c1 {h1mgmt0ip}"))
        logging.debug(r.conrepl.cmd_raises(f"ping -w1 -c1 {h1ip}"))

    # Will use SSH.
    for r, h1ip in zip(rs, h1_r1ips):
        logging.debug(r.cmd_raises("ping -w1 -c1 192.168.0.254"))
        logging.debug(r.cmd_raises(f"ping -w1 -c1 {h1mgmt0ip}"))
        logging.debug(r.cmd_raises(f"ping -w1 -c1 {h1ip}"))

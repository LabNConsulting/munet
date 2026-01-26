# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing of basic IP forwrading."

import ipaddress
import logging
from munet.testing.util import retry


@retry(retry_timeout=60, retry_sleep=1)
def check_route(r, addr):
    addr = ipaddress.ip_address(addr)
    vs = "-4" if addr.version == 4 else "-6"
    o = r.cmd_raises(f"ip {vs} route get {addr}")
    assert str(addr) in o, f"Missing route for {addr}"


def test_basic_ping(unet):
    r1 = unet.hosts["r1"]
    r3 = unet.hosts["r3"]

    #
    # IPv4
    #

    this_ip = r1.get_intf_addr("eth0", ipv6=False).ip
    other_ip = r3.get_intf_addr("eth0", ipv6=False).ip
    check_route(r1, other_ip)
    check_route(r3, this_ip)

    o = r1.cmd_nostatus(f"ping -c1 {other_ip}", warn=False)
    logging.debug("pump prime ping r3 output: %s", o)
    o = r1.cmd_raises(f"ping -c1 {other_ip}")
    logging.debug("ping r3 output: %s", o)

    #
    # IPv6
    #

    this_ip = r1.get_intf_addr("eth0", ipv6=True).ip
    other_ip = r3.get_intf_addr("eth0", ipv6=True).ip
    check_route(r1, other_ip)
    check_route(r3, this_ip)

    o = r1.cmd_nostatus(f"ping -c1 {other_ip}", warn=False)
    logging.debug("pump prime ping r3 output: %s", o)
    o = r1.cmd_raises(f"ping -c1 {other_ip}")
    logging.debug("ping r3 output: %s", o)

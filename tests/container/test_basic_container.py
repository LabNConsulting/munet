# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing use of containers in munet."

import logging

import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_containers_up(unet):
    r2 = unet.hosts["r2"]
    assert r2.cmd_p is not None
    assert r2.cmd_p.returncode is None


async def test_ping_the_container(unet):
    other_ip = unet.hosts["r2"].get_intf_addr("eth0").ip
    o = await unet.hosts["r1"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.debug("ping output: %s", o)

    other_ip = unet.hosts["r2"].get_intf_addr("eth1").ip
    o = await unet.hosts["r1"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.debug("ping output: %s", o)


async def test_ping_from_container(unet):
    other_ip = unet.hosts["r1"].get_intf_addr("eth0").ip
    o = await unet.hosts["r2"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.debug("ping output: %s", o)

    other_ip = unet.hosts["r1"].get_intf_addr("eth1").ip
    o = await unet.hosts["r2"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.debug("ping output: %s", o)


async def test_container_mounts(unet):
    await unet.hosts["r2"].async_cmd_raises("echo foobar > /mytmp/foobar.txt")
    o = await unet.hosts["r2"].async_cmd_raises("cat /mytmp/foobar.txt")
    assert o == "foobar\n"

    o = await unet.hosts["r2"].async_cmd_raises("df -T ")
    logging.debug("DF:\n%s\n", o)

    await unet.hosts["r2"].async_cmd_raises("echo foobaz > /mybind/foobar.txt")
    o = await unet.hosts["r2"].async_cmd_raises("cat /mybind/foobar.txt")
    assert o == "foobaz\n"

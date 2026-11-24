# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 03 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"Testing of basic background command API."


import asyncio
import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_background_capture(unet):
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]

    oifname = 'eth2'
    oip = r2.get_intf_addr(oifname).ip
    pid = r1.background_cmd_start(f"ping -i 0.1 {oip}")

    rv, out, _ = await r2.async_cmd_status("tshark -i any -c 3 -f icmp")
    assert rv == 0
    assert "Echo (ping) request" in out

    rv, out, _ = r1.background_cmd_end_status(pid, timeout=5)

    assert rv != 0  # This process was forcefully terminated!
    assert "bytes from 10.0.1.2" in out


async def test_background_early_finish(unet):
    r2 = unet.hosts["r2"]

    pid = r2.background_cmd_start("echo foo")

    await asyncio.sleep(1)

    rv, out, _ = r2.background_cmd_end_status(pid, timeout=5)
    assert rv == 0  # This process exited normally!
    assert "foo" in out


async def test_background_stdin(unet):
    r2 = unet.hosts["r2"]

    pid = r2.background_cmd_start("cat", stdin="hello world")

    await asyncio.sleep(1)

    rv, out, _ = r2.background_cmd_end_status(pid, timeout=5)
    assert rv == 0  # This process was forcefully terminated!
    assert "hello world" in out


async def test_background_pcaps(unet):
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]

    r1cap = unet.start_pcap("r1:eth1")
    r2cap = unet.start_pcap("r2:eth2")
    netcap = unet.start_pcap("net0")

    oifname = 'eth2'
    oip = r2.get_intf_addr(oifname).ip
    await r1.async_cmd_status(f"ping -i 0.1 {oip} -c 10")

    _, o, _ = r1.cmd_status(f"tshark -r {r1cap}")
    assert "Echo (ping) request" in o
    _, o, _ = r2.cmd_status(f"tshark -r {r2cap}")
    assert "Echo (ping) request" in o
    _, o, _ = unet.cmd_status(f"tshark -r {netcap}")
    assert "Echo (ping) request" in o

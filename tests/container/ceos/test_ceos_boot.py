# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Exercise cEOS boot preparation with the CI container image."""

import pytest


@pytest.mark.asyncio
async def test_ceos_boot(unet_perfunc_share):
    ceos = unet_perfunc_share.hosts["ceos-test"]
    init, env_arg = (ceos.rundir / "container.out").read_text().splitlines()
    assert init == "/sbin/init"
    assert env_arg.startswith("systemd.setenv=INTFTYPE=")
    assert "eth" in env_arg
    assert ceos.cmd_raises("cat /mnt/flash/startup-config") == "hostname ceos-test\n"
    assert ceos.cmd_raises("cat /mnt/flash/system_mac_address") == "00:1c:73:11:22:33\n"

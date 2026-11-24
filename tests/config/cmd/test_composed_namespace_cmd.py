# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Exercise lifecycle composition in a real Linux namespace."""

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("unet_perfunc_share", ["munet-composed"], indirect=True)
async def test_config_composed_commands(unet_perfunc_share):
    node = unet_perfunc_share.hosts["h-composed"]
    check_kind_running = 'kill -0 "$(cat kind.pid)"'
    node.cmd_raises(check_kind_running)
    assert node.cmd_raises("cat cmd.1.out cmd.2.out") == "kind\nnode\n"
    await node.async_cleanup_cmd()
    assert node.cmd_raises("cat cleanup-order") == "node\nkind\n"
    node.cmd_raises(check_kind_running)

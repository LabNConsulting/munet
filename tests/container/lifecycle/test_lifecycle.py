# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Lifecycle commands exercised with the CI container image."""

import pytest


@pytest.mark.asyncio
async def test_container_lifecycles(unet_perfunc_share):
    unet = unet_perfunc_share
    composed = unet.hosts["composed"]
    assert (composed.rundir / "container.out").read_text() == "booted\n"
    assert (composed.rundir / "cmd.1.out").read_text() == "kind\n"
    assert (composed.rundir / "cmd.2.out").read_text() == "node\n"
    composed.cmd_raises('kill -0 "$(cat /kind.pid)"')
    runtime = composed.cmd_p

    legacy = unet.hosts["legacy"]
    assert (legacy.rundir / "container.out").read_text() == "legacy-boot\n"
    assert legacy.cmd_raises("cat /legacy-count") == "boot\n"
    assert (legacy.rundir / "cmd.2.out").read_text() == "follow-up\n"

    image_default = unet.hosts["empty-boot"]
    assert (image_default.rundir / "cmd.out").read_text() == "empty-boot\n"
    assert (
        unet.hosts["single"].rundir / "container.out"
    ).read_text() == "merged-shell\n"
    assert (
        unet.hosts["node-boot"].rundir / "container.out"
    ).read_text() == "node-boot\n"

    await unet.async_delete()
    assert (composed.rundir / "results/cleanup-order").read_text() == "node\nkind\n"
    assert runtime.returncode is not None

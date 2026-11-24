# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 03 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"Testing of basic background command API automatic cleanup."


import asyncio
import os
import signal
from pathlib import Path

import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_background_process_cleanup(unet_function):
    unet = unet_function
    r1 = unet.hosts["r1"]

    pid = r1.background_cmd_start("ping 10.0.1.2 -i 0.1")

    await asyncio.sleep(1)

    # Ensure that process still exists
    os.kill(pid, 0)

    # We let the munet topology clean up the background command.
    await unet.async_delete()

    assert len(unet.background_cmds) == 0

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pass
    else:
        assert False, f"Process {pid} survived cleanup"


@pytest.mark.parametrize("parent_waits", [True, False])
async def test_background_process_group_cleanup(unet_function, parent_waits):
    unet = unet_function
    r1 = unet.hosts["r1"]

    heartbeat_file = f"/tmp/unet_child_heartbeat_{parent_waits}.log"
    pid = r1.background_cmd_start(
        f"""(while true; do date +%s%N > {heartbeat_file}; sleep 0.1; done) & """
        f"""wait"""
    )

    await asyncio.sleep(1)

    # Ensure that process and pgroup still exists
    os.kill(pid, 0)
    pgid = os.getpgid(pid)
    assert pgid != os.getpgrp()
    assert pgid == os.getpgid(pid)
    os.killpg(pgid, 0)

    # Force child to become an orphan process
    if parent_waits:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    # Ensure that the orphan child is still running
    for _ in range(50):
        if os.path.exists(heartbeat_file):
            break
        await asyncio.sleep(0.1)
    assert os.path.exists(heartbeat_file), "Child never started"

    before = Path(heartbeat_file).read_text(encoding="utf-8").strip()
    await asyncio.sleep(0.5)
    after = Path(heartbeat_file).read_text(encoding="utf-8").strip()
    assert after != before

    # We let the munet topology clean up the background command.
    await unet.async_delete()

    assert len(unet.background_cmds) == 0

    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        pass
    else:
        assert False, f"Process group {pid} survived cleanup"

    # Ensure that the orphan child has died
    before = Path(heartbeat_file).read_text(encoding="utf-8").strip()
    await asyncio.sleep(0.5)
    after = Path(heartbeat_file).read_text(encoding="utf-8").strip()
    assert after == before, "Child process survived cleanup"

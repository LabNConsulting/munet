# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 02 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Additional background-command tests related to return codes."""

import sys

import pytest

from munet.base import CalledProcessError

# All tests are coroutines
pytestmark = pytest.mark.asyncio

@pytest.mark.parametrize("exit_code", [0, 23])
async def test_background_cmd_end_with_status(unet, exit_code):
    pid = unet.background_cmd_start(
        [sys.executable, "-c", f"import sys; print('result'); sys.exit({exit_code})"]
    )
    bg = unet.background_cmds[pid]
    try:
        # Premtively reaps the process. Subprocesses should
        # preserve the return value into the end_status call.
        assert bg.p.wait(timeout=3) == exit_code

        # Intentionally omit the timeout keyword.
        rv, stdout, stderr = unet.background_cmd_end_status(pid)
        assert rv == exit_code
        assert "result" in stdout
        assert not stderr
        assert pid not in unet.background_cmds
        assert bg.stdin_file.closed
        assert bg.stdout_file.closed
        assert bg.stderr_file.closed
    finally:
        if pid in unet.background_cmds:
            try:
                unet.background_cmd_end_status(pid, timeout=0.3)
            except Exception:
                pass


async def test_background_cmd_end_with_raises(unet):
    pid = unet.background_cmd_start(
        [sys.executable, "-c", "import sys; print('bad'); sys.exit(23)"]
    )
    bg = unet.background_cmds[pid]
    try:
        assert bg.p.wait(timeout=3) == 23
        with pytest.raises(CalledProcessError) as caught:
            unet.background_cmd_end_raises(pid)
        assert caught.value.returncode == 23
        assert "bad" in caught.value.output
        assert pid not in unet.background_cmds
    finally:
        if pid in unet.background_cmds:
            try:
                unet.background_cmd_end_status(pid, timeout=0.3)
            except Exception:
                pass


async def test_background_cmd_end_when_running(unet):
    pid = unet.background_cmd_start(
        [sys.executable, "-c", "import time; time.sleep(60)"]
    )
    try:
        # Exercises the default timeout while the child still needs signalling.
        rv, _, _ = unet.background_cmd_end_status(pid)
        assert rv in (-1, -9)  # SIGHUP or SIGKILL
    finally:
        if pid in unet.background_cmds:
            try:
                unet.background_cmd_end_status(pid, timeout=0.3)
            except Exception:
                pass

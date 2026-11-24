# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 02 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Regression tests for Commander PID, process, and process-group cleanup."""

import asyncio
import os
import select
import signal
import subprocess
import sys
import time

import pytest

from munet.base import Commander, Timeout

# pylint: disable=redefined-outer-name

@pytest.fixture
def commander():
    """A Commander needs no network topology for process cleanup."""
    return Commander("cleanup-tests")


def _python(code, *args):
    return [sys.executable, "-u", "-c", code, *map(str, args)]


def _stop_sync(proc):
    """Avoid leaking test subprocesses if an assertion fails."""
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=3)
    if proc.stdout is not None:
        proc.stdout.close()
    if proc.stderr is not None:
        proc.stderr.close()


async def _stop_async(proc):
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    await asyncio.wait_for(proc.wait(), timeout=3)


def _sync_readline(proc, timeout=3):
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    assert ready, f"process {proc.pid} did not produce a line"
    return proc.stdout.readline()


def _wait_unreaped(pid, timeout=3):
    """Observe child exit without consuming its wait status (Linux)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = os.waitid(
            os.P_PID,
            pid,
            os.WEXITED | os.WNOHANG | os.WNOWAIT,
        )
        if info is not None:
            return
        time.sleep(0.01)
    pytest.fail(f"child {pid} did not exit")


async def test_timeout_zero_runs_once():
    assert list(Timeout(0)) == [0]
    assert list(Timeout(-1)) == [0]


@pytest.mark.parametrize("exit_code", [0, 42])
@pytest.mark.parametrize("async_cleanup", [False, True])
async def test_cleanup_pid_already_reaped_popen(commander, exit_code, async_cleanup):
    proc = subprocess.Popen(_python(f"import sys; sys.exit({exit_code})"))
    try:
        assert proc.wait(timeout=3) == exit_code
        if async_cleanup:
            rv = await commander.async_cleanup_pid(proc.pid, proc=proc, wait_sec=0)
        else:
            rv = commander.cleanup_pid(proc.pid, proc=proc, wait_sec=0)
        assert rv == exit_code
        assert proc.returncode == exit_code
    finally:
        _stop_sync(proc)


@pytest.mark.parametrize("exit_code", [0, 42])
async def test_cleanup_pid_already_reaped_asyncio(commander, exit_code):
    proc = await asyncio.create_subprocess_exec(
        *_python(f"import sys; sys.exit({exit_code})")
    )
    try:
        assert await asyncio.wait_for(proc.wait(), timeout=3) == exit_code
        rv = await commander.async_cleanup_pid(proc.pid, proc=proc, wait_sec=0)
        assert rv == exit_code
    finally:
        await _stop_async(proc)


@pytest.mark.parametrize("async_cleanup", [False, True])
@pytest.mark.parametrize("ignore_hup", [False, True])
async def test_cleanup_pid_signal_exit_status(
    commander, async_cleanup, ignore_hup
):
    code = (
        "import signal, time\n"
        + (
            "signal.signal(signal.SIGHUP, signal.SIG_IGN)\n"
            if ignore_hup
            else "signal.signal(signal.SIGHUP, signal.SIG_DFL)\n"
        )
        + "print('READY', flush=True)\n"
        + "while True: time.sleep(1)\n"
    )
    proc = subprocess.Popen(
        _python(code), stdout=subprocess.PIPE, text=True
    )
    try:
        # The child has installed its signal handling before we send SIGHUP.
        assert _sync_readline(proc).strip() == "READY"
        if async_cleanup:
            rv = await commander.async_cleanup_pid(
                proc.pid, proc=proc, wait_sec=0.3
            )
        else:
            rv = commander.cleanup_pid(proc.pid, proc=proc, wait_sec=0.3)
        expected = -signal.SIGKILL if ignore_hup else -signal.SIGHUP
        assert rv == expected
        assert proc.returncode == expected
    finally:
        _stop_sync(proc)


@pytest.mark.parametrize("exit_code", [0, 37])
def test_reap_pid_popen(commander, exit_code):
    proc = subprocess.Popen(_python(f"import sys; sys.exit({exit_code})"))
    try:
        assert proc.wait(timeout=3) == exit_code
        assert commander.reap_pid(proc.pid, proc) == (True, exit_code)
    finally:
        _stop_sync(proc)


@pytest.mark.parametrize("exit_code", [0, 37])
async def test_reap_pid_asyncio(commander, exit_code):
    proc = await asyncio.create_subprocess_exec(
        *_python(f"import sys; sys.exit({exit_code})")
    )
    try:
        assert await asyncio.wait_for(proc.wait(), timeout=3) == exit_code
        assert commander.reap_pid(proc.pid, proc) == (True, exit_code)
    finally:
        await _stop_async(proc)


@pytest.mark.skipif(not hasattr(os, "WNOWAIT"), reason="requires waitid/WNOWAIT")
@pytest.mark.parametrize("exit_code", [0, 37])
def test_reap_pid_raw_waitpid(commander, exit_code):
    # Do not call Popen.wait/poll: reap_pid is the sole waiter here.
    proc = subprocess.Popen(_python(f"import sys; sys.exit({exit_code})"))
    try:
        _wait_unreaped(proc.pid)
        assert commander.reap_pid(proc.pid) == (True, exit_code)
        assert commander.reap_pid(proc.pid) == (True, None)  # ECHILD
    finally:
        _stop_sync(proc)


async def test_cleanup_pid_rejects_mismatched_popen(commander):
    proc = subprocess.Popen(_python("pass"))
    try:
        with pytest.raises(ValueError, match="proc.pid"):
            commander.cleanup_pid(proc.pid + 1, proc=proc)
        with pytest.raises(ValueError, match="proc.pid"):
            await commander.async_cleanup_pid(proc.pid + 1, proc=proc)
    finally:
        _stop_sync(proc)


async def test_sync_cleanup_pid_rejects_asyncio(commander):
    proc = await asyncio.create_subprocess_exec(*_python("pass"))
    try:
        with pytest.raises(ValueError, match="Async process"):
            commander.cleanup_pid(proc.pid, proc=proc)
    finally:
        await _stop_async(proc)


@pytest.mark.parametrize("kind", ["popen", "asyncio"])
async def test_async_cleanup_proc_different_signal_pid(commander, kind):
    # An nsenter-like wrapper waits for its child. The signal must go to the
    # child, while the wrapper's Popen/asyncio Process owns reaping.
    wrapper = """
import subprocess
import sys
child = subprocess.Popen(
    [sys.executable, '-c', 'import time; time.sleep(60)'],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(child.pid, flush=True)
child.wait()
"""
    if kind == "popen":
        proc = subprocess.Popen(
            _python(wrapper), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            *_python(wrapper), stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, start_new_session=True
        )

    try:
        if kind == "popen":
            child_pid = int(_sync_readline(proc).strip())
        else:
            line = await asyncio.wait_for(proc.stdout.readline(), 3)
            child_pid = int(line.strip())
        assert child_pid != proc.pid
        result = await asyncio.wait_for(
            commander.async_cleanup_proc(proc, pid=child_pid), timeout=5
        )
        assert result is None
        assert proc.returncode == 0
    finally:
        # Safely kill the wrapper and any surviving descendants together.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if kind == "popen":
            _stop_sync(proc)
        else:
            await _stop_async(proc)


@pytest.mark.parametrize("kind", ["popen", "asyncio"])
async def test_async_cleanup_proc_direct_process(commander, kind):
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGHUP, signal.SIG_DFL)\n"
        "print('READY', flush=True)\n"
        "while True: time.sleep(1)\n"
    )
    if kind == "popen":
        proc = subprocess.Popen(
            _python(code), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            *_python(code), stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    try:
        if kind == "popen":
            assert _sync_readline(proc).strip() == "READY"
        else:
            line = await asyncio.wait_for(proc.stdout.readline(), 3)
            assert line.strip() == b"READY"
        assert await asyncio.wait_for(commander.async_cleanup_proc(proc), 5) is None
        assert proc.returncode == -signal.SIGHUP
    finally:
        if kind == "popen":
            _stop_sync(proc)
        else:
            await _stop_async(proc)

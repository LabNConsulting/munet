# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Cleanup order and coordination with independent process waiters."""

import asyncio
import signal
from unittest.mock import AsyncMock

import pytest

from munet.lifecycle import LifecycleStage


async def test_reverse_cleanup_continues_after_failed_hook(
    unet_perfunc_share, tmp_path, caplog
):
    """Clean up entered stages once, even after startup and a cleanup hook fail."""
    order = tmp_path / "order"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(cleanup_cmd=f"echo first >> {order}"),
            LifecycleStage(shell=False, cleanup_cmd="/no-such-command"),
            LifecycleStage(
                shell=False,
                cmd_file="/also-missing",
                cleanup_cmd=f"/usr/bin/touch {tmp_path / 'failed-cleanup'}",
            ),
            LifecycleStage(cleanup_cmd=f"echo never >> {order}"),
        ],
    )
    with pytest.raises(FileNotFoundError):
        await node.run_cmd()
    await node.async_cleanup_cmd()
    await node.async_cleanup_cmd()
    assert (tmp_path / "failed-cleanup").exists()
    assert order.read_text() == "first\n"
    assert "stage 2 cleanup-cmd" in caplog.text


async def test_overlapping_cleanup_and_finalization_are_once(
    unet_perfunc_share, tmp_path, monkeypatch
):
    """Run hooks in reverse order and stop the process once across callers."""
    order = tmp_path / "order"
    release = tmp_path / "release"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(cmd="exec sleep 60", cleanup_cmd=f"echo 1 >> {order}"),
            LifecycleStage(
                cleanup_cmd=f"echo 2 >> {order}\n"
                f"while [ ! -f {release} ]; do sleep .01; done"
            ),
        ],
    )
    await node.run_cmd()
    [record] = node.cmd_procs

    async def wait_for_cleanup():
        while not order.exists():
            await asyncio.sleep(0.01)

    cleanup_proc = AsyncMock(wraps=node.async_cleanup_proc)
    monkeypatch.setattr(node, "async_cleanup_proc", cleanup_proc)
    caller = asyncio.create_task(node.async_cleanup_cmd())
    tasks = [caller]
    try:
        await asyncio.wait_for(wait_for_cleanup(), 5)
        overlap = asyncio.create_task(node.async_cleanup_cmd())
        tasks.append(overlap)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        tasks.extend(asyncio.create_task(node._finalize_lifecycle()) for _ in range(2))
        await asyncio.sleep(0)
        assert not overlap.done()
        assert record.proc.returncode is None
        assert cleanup_proc.await_count == 0
    finally:
        release.touch()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
    for task in tasks[1:]:
        task.result()
    assert order.read_text() == "2\n1\n"
    assert cleanup_proc.await_count == 1
    assert record.returncode == -signal.SIGHUP


async def test_topology_cleanup_before_coverage_and_destruction(
    unet_perfunc_share, monkeypatch, tmp_path
):
    """Run cleanup hooks before coverage and keep nodes alive until it ends."""
    hook = tmp_path / "cleanup"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(cmd="exec sleep 60", cleanup_cmd=f"touch {hook}")
        ],
    )
    [watcher] = await unet_perfunc_share.run()
    events = []

    async def coverage():
        assert hook.exists()
        assert node.cmd_p is not None
        events.append("coverage")

    async def coverage_finish():
        assert events == ["coverage"]
        assert not node.deleting
        assert node.cmd_p is not None
        events.append("coverage-finish")

    monkeypatch.setattr(unet_perfunc_share, "coverage_finish", coverage_finish)
    monkeypatch.setattr(unet_perfunc_share.cfgopt.option, "coverage", True)
    monkeypatch.setattr(node, "gather_coverage_data", coverage, raising=False)
    await unet_perfunc_share.async_delete()
    assert events == ["coverage", "coverage-finish"]
    assert node.deleting
    assert unet_perfunc_share.hosts == {}
    assert watcher.result() == -signal.SIGHUP


@pytest.mark.parametrize("already_exited", [True, False])
async def test_natural_exit_with_active_waiter(
    unet_perfunc_share, tmp_path, monkeypatch, already_exited
):
    """Preserve a natural exit status before or during process cleanup."""
    release = tmp_path / "release"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(cmd=f"while [ ! -f {release} ]; do sleep .01; done; exit 31")
        ],
    )
    await node.run_cmd()
    [record] = node.cmd_procs
    if already_exited:
        release.touch()
        assert await asyncio.wait_for(record.task, 2) == 31
    else:
        original = node.async_cleanup_pid

        async def exit_during_cleanup(*args, **kwargs):
            release.touch()
            # Enter cleanup with a live proc, before it exits naturally.
            await asyncio.wait_for(asyncio.shield(record.task), 2)
            return await original(*args, **kwargs)

        monkeypatch.setattr(node, "async_cleanup_pid", exit_during_cleanup)

    await asyncio.wait_for(node._finalize_lifecycle(), 3)
    assert record.returncode == record.task.result() == 31
    assert node.cmd_procs == [record]


@pytest.mark.parametrize("cancel_watcher", [True, False])
async def test_kill_escalation_preserves_exit_status(
    unet_perfunc_share, tmp_path, cancel_watcher
):
    """Record SIGKILL after an ignored SIGHUP, even if the watcher was cancelled."""
    started = tmp_path / "started"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(
                cmd=f"trap '' HUP; touch {started}; exec sleep 60",
                ready_cmd=f"test -f {started}",
            )
        ],
    )
    await node.run_cmd()
    [record] = node.cmd_procs
    if cancel_watcher:
        record.task.cancel()
        await asyncio.gather(record.task, return_exceptions=True)
    await asyncio.wait_for(node._finalize_lifecycle(), 40)
    assert record.returncode == record.proc.returncode == -signal.SIGKILL
    if not cancel_watcher:
        assert record.task.result() == -signal.SIGKILL


async def test_cleanup_timeout_does_not_discard_watcher(
    unet_perfunc_share, monkeypatch, caplog
):
    """Log a cleanup timeout once and let the watcher report the eventual exit."""
    node = unet_perfunc_share.add_l3_node(
        "r1", lifecycle_stages=[LifecycleStage(cmd="exec sleep 60")]
    )
    await node.run_cmd()
    [record] = node.cmd_procs
    timeout = AsyncMock(side_effect=TimeoutError("simulated signal timeout"))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(node, "async_cleanup_pid", timeout)
            await asyncio.wait_for(node._finalize_lifecycle(), 1)
            await node._finalize_lifecycle()
            assert timeout.await_count == 1
            assert "SIGKILL timeout" in caplog.text
            assert not record.task.done()
    finally:
        await node.async_cleanup_proc(record.proc, record.pid)
        await asyncio.wait_for(record.task, 2)
    assert record.returncode == record.task.result()


async def test_alternate_nsenter_child_pid(unet_perfunc_share):
    """Stop the nsenter child by its PID and preserve the watched exit status."""
    node = unet_perfunc_share.add_l3_node(
        "r1", lifecycle_stages=[LifecycleStage(cmd="exec sleep 60")]
    )
    await asyncio.wait_for(node.run_cmd(), 5)
    [record] = node.cmd_procs
    assert record.pid is not None and record.pid != record.proc.pid
    assert node.pid_exists(record.pid)
    await asyncio.wait_for(node._finalize_lifecycle(), 3)
    assert not node.pid_exists(record.pid)
    assert record.task.done()
    assert record.returncode == record.task.result()


async def test_stage_processes_finalize_concurrently(unet_perfunc_share, monkeypatch):
    """Start cleanup for both stage processes before allowing either to finish."""
    node = unet_perfunc_share.add_l3_node(
        "r1", lifecycle_stages=[LifecycleStage(cmd="exec sleep 60")] * 2
    )
    await node.run_cmd()
    entered = asyncio.Queue()
    release = asyncio.Event()
    cleanup_proc = node.async_cleanup_proc
    stage_pids = {record.proc.pid for record in node.cmd_procs}

    async def wait_then_cleanup(proc, pid=None):
        if proc is not None and proc.pid in stage_pids:
            entered.put_nowait(proc.pid)
            await release.wait()
        return await cleanup_proc(proc, pid)

    monkeypatch.setattr(node, "async_cleanup_proc", wait_then_cleanup)
    finalizer = asyncio.create_task(node.async_delete())
    try:
        pids = {await asyncio.wait_for(entered.get(), 2) for _ in stage_pids}
        assert pids == stage_pids
        assert not finalizer.done()
    finally:
        release.set()
        await asyncio.wait_for(finalizer, 3)

    assert [record.returncode for record in node.cmd_procs] == [-signal.SIGHUP] * 2

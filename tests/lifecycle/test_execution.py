# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Stage execution, readiness, and topology ownership."""

import asyncio
import io
import sys

import pytest

from munet import cli
from munet.lifecycle import LifecycleStage


async def run_topology(unet):
    return await asyncio.wait_for(unet.run(), 5)


async def test_two_live_commands_and_independent_output(unet_perfunc_share):
    """Keep both startup processes alive with separate logs and exit watchers."""
    kind_up = unet_perfunc_share.rundir / "kind-up"
    node_up = unet_perfunc_share.rundir / "node-up"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(
                cmd=f"echo kind; echo kind-err >&2; touch {kind_up}; exec sleep 60",
                ready_cmd=f"test -f {kind_up}",
            ),
            LifecycleStage(
                cmd=f"echo node; echo node-err >&2; touch {node_up}; exec sleep 60",
                ready_cmd=f"test -f {node_up}",
            ),
        ],
    )
    tasks = await run_topology(unet_perfunc_share)
    assert (
        tasks
        == unet_perfunc_share.process_exit_tasks
        == [p.task for p in node.cmd_procs]
    )
    assert len(tasks) == 2
    assert not any(t.done() for t in tasks)
    for i, body in enumerate(("kind", "node"), 1):
        assert (node.rundir / f"cmd.{i}.out").read_text() == f"{body}\n"
        assert (node.rundir / f"cmd.{i}.err").read_text() == f"{body}-err\n"


async def test_exit_status_is_diagnostic_and_readiness_keeps_polling(
    unet_perfunc_share,
):
    """Record a startup exit and keep polling before entering the next stage."""
    ready = unet_perfunc_share.rundir / "ready"
    checks = unet_perfunc_share.rundir / "checks"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(cmd="exit 17", ready_cmd=f"touch {checks}; test -f {ready}"),
            LifecycleStage(cmd="exit 23"),
        ],
    )
    startup = asyncio.create_task(run_topology(unet_perfunc_share))
    try:
        while not unet_perfunc_share.process_exit_tasks or not checks.exists():
            if startup.done():
                await startup
            await asyncio.sleep(0.01)
        assert await asyncio.wait_for(node.cmd_procs[0].task, 2) == 17
        assert not node.stage_states[0].ready
        assert not node.stage_states[1].entered
        ready.touch()
        watchers = await startup
        assert await asyncio.gather(*watchers) == [17, 23]
        assert [p.returncode for p in node.cmd_procs] == [17, 23]
    finally:
        startup.cancel()
        await asyncio.gather(startup, return_exceptions=True)


async def test_readiness_only_stage_and_inter_node_concurrency(unet_perfunc_share):
    """Let another node advance while a readiness-only stage waits for it."""
    ready = unet_perfunc_share.rundir / "other-node-stage"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(ready_cmd=f"test -f {ready}"),
            LifecycleStage(cmd="echo r1"),
        ],
    )
    other = unet_perfunc_share.add_l3_node(
        "r2", lifecycle_stages=[LifecycleStage(), LifecycleStage(cmd=f"touch {ready}")]
    )
    tasks = await run_topology(unet_perfunc_share)
    await asyncio.gather(*tasks)
    assert node.stage_states[0].ready and other.stage_states[0].ready
    for host in (node, other):
        assert not (host.rundir / "cmd.1.out").exists()
        assert (host.rundir / "cmd.2.out").is_file()


async def test_file_precedence_and_generic_cli_shell(unet_perfunc_share, tmp_path):
    """Prefer cmd-file, substitute its contents, and preserve ordinary shells."""
    script = tmp_path / "startup.py"
    script.write_text(f"#!{sys.executable}\nprint('%NAME%')\n")
    node = unet_perfunc_share.add_l3_node(
        "r1", config={"cmd": "exit 99", "cmd-file": str(script)}
    )
    await asyncio.gather(*(await run_topology(unet_perfunc_share)))
    assert (node.rundir / "cmd.out").read_text() == "r1\n"
    assert (node.rundir / "cmd.err").read_text() == ""

    second = unet_perfunc_share.add_l3_node(
        "r2",
        lifecycle_stages=[
            LifecycleStage(cmd_file=str(script), cmd="exit 99"),
            LifecycleStage(cmd="print('python')", shell=sys.executable),
        ],
        config={"shell": sys.executable},
    )
    assert await (await second.run_cmd()).wait() == 0
    assert (second.rundir / "cmd.2.out").read_text() == "python\n"
    assert second.cmd_status("printf '%s' bash")[1] == "bash"
    assert (await second.async_cmd_status("printf '%s' async"))[1] == "async"
    output = io.StringIO()
    await cli.run_command(
        unet_perfunc_share, output, "printf '%s' cli", "{}", False, ["r2"], False, []
    )
    assert output.getvalue() == "cli"


async def test_timeout_cancels_siblings_preserving_started_processes(
    unet_perfunc_share,
):
    """Cancel sibling startup on a timeout and keep live processes for teardown."""
    gate = unet_perfunc_share.rundir / "checking"
    cancelled = unet_perfunc_share.rundir / "cancelled"
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(
                cmd="exec sleep 60", ready_cmd=f"touch {gate}; exec sleep 60"
            ),
            LifecycleStage(cmd="echo never"),
        ],
    )
    bad = unet_perfunc_share.add_l3_node(
        "r2",
        lifecycle_stages=[
            LifecycleStage(
                ready_cmd=f"test -f {gate} && false",
                ready_timeout=1,
                cleanup_cmd=f"touch {cancelled}",
            ),
            LifecycleStage(cmd="echo never"),
        ],
    )
    with pytest.raises(asyncio.TimeoutError, match=r"r2.*stage 1"):
        await run_topology(unet_perfunc_share)
    assert gate.exists() and not cancelled.exists()
    assert not node.stage_states[1].entered and not bad.stage_states[1].entered
    [watcher] = unet_perfunc_share.process_exit_tasks
    assert watcher is node.cmd_procs[0].task
    assert not watcher.done()
    await bad.async_cleanup_cmd()
    assert cancelled.exists()


async def test_failed_dispatch_enters_stage(unet_perfunc_share):
    """Record a failed stage as entered so it remains eligible for cleanup."""
    node = unet_perfunc_share.add_l3_node(
        "r1",
        lifecycle_stages=[
            LifecycleStage(cleanup_cmd="true"),
            LifecycleStage(cmd_file="/no-such-command"),
            LifecycleStage(cmd="echo never"),
        ],
    )
    with pytest.raises(FileNotFoundError):
        await run_topology(unet_perfunc_share)
    assert [s.entered for s in node.stage_states] == [True, True, False]


async def test_node_without_commands_returns_no_watchers(unet_perfunc_share):
    """Mark a node with no commands ready and return an empty watcher list."""
    node = unet_perfunc_share.add_l3_node("r1")
    assert await run_topology(unet_perfunc_share) == []
    assert node.stage_states[0].ready


@pytest.mark.parametrize("shell", [True, False, "/bin/bash"])
async def test_explicit_shell_overrides_file_shebang(
    unet_perfunc_share, tmp_path, shell
):
    """Run a command file with the explicit shell setting despite a bad shebang."""
    script = tmp_path / "wrong-shebang"
    script.write_text("#!/no-such-interpreter\n/bin/echo override\n")
    node = unet_perfunc_share.add_l3_node(
        "r1", lifecycle_stages=[LifecycleStage(cmd_file=str(script), shell=shell)]
    )
    proc = await node.run_cmd()
    assert await proc.wait() == 0
    assert (node.rundir / "cmd.out").read_text() == "override\n"

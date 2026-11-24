# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Lifecycle configuration and precedence."""

import pytest

from munet.config import config_subst
from munet.config import merge_kind_config
from munet.lifecycle import resolve_lifecycle
from munet.parser import load_kinds


def resolve(kind, node, name="r1"):
    context = dict(name=name, rundir=f"/run/{name}", configdir="/topology")
    merged = config_subst(merge_kind_config(kind, node), **context)
    return resolve_lifecycle(node, kind, merged, **context)


def test_default_stage():
    """Use one merged stage by default and skip startup with no command.

    The node command overrides the kind's command and inherits its other settings.
    """
    [empty] = resolve({}, {})
    assert not empty.has_startup
    kind = {"cmd": "kind", "shell": False, "ready-timeout": 10}
    [stage] = resolve(kind, {"cmd": "node"})
    assert stage.cmd == "node"
    assert stage.shell is False
    assert stage.ready_timeout == 10


@pytest.mark.parametrize("name", ["r1", "r2"])
def test_composed_stage_substitution(name):
    """Resolve the kind stage first, then the node stage with its own settings.

    Substitute each node's values without mutating the shared kind definition.
    """
    kind = {
        "merge": ["commands"],
        "cmd": "kind %NAME%",
        "shell": "/bin/dash",
        "ready-timeout": 7,
        "cleanup-cmd": "rm %RUNDIR%/kind",
    }
    node = {"cmd-file": "%CONFIGDIR%/run", "ready-cmd": "test -f %RUNDIR%/ready"}
    first, second = resolve(kind, node, name)
    assert first.cmd == f"kind {name}"
    assert first.shell == "/bin/dash"
    assert first.ready_timeout == 7
    assert first.cleanup_cmd == f"rm /run/{name}/kind"
    assert second.cmd_file == "/topology/run"
    assert second.ready_cmd == f"test -f /run/{name}/ready"
    assert second.shell is None
    assert kind["cmd"] == "kind %NAME%"


def test_effective_kind_supplies_composed_command(tmp_path):
    """Compose commands from the winning kind alongside ordinary merge rules."""
    for directory, contents in (
        ("first", "{name: router, cmd: shadowed}"),
        (
            "second",
            "{name: router, merge: [commands, cap-add], "
            "cmd: 'kind %NAME%', cap-add: [A]}",
        ),
    ):
        source = tmp_path / directory
        source.mkdir()
        (source / "kinds.yaml").write_text(f"kinds: [{contents}]\n")

    kinds = load_kinds(None, [str(tmp_path / src) for src in ("first", "second")])
    kind = kinds["kinds"]["router"]
    node = {"name": "r1", "kind": "router", "cmd": "node", "cap-add": ["B"]}
    assert merge_kind_config(kind, node)["cap-add"] == ["A", "B"]
    assert [stage.cmd for stage in resolve(kind, node)] == ["kind r1", "node"]

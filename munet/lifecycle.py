# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 23 2026, Liam Brady <lbrady@labn.net>
#
# Copyright (c) 2026, LabN Consulting, L.L.C.
#
"""Configuration and state for node lifecycle commands."""

from __future__ import annotations

import asyncio

from dataclasses import dataclass
from dataclasses import fields

from .config import config_subst


@dataclass(frozen=True)
class LifecycleStage:
    """Lifecycle settings from one configuration source."""

    cmd: str | None = None
    cmd_file: str | None = None
    ready_cmd: str | None = None
    ready_timeout: int | None = None
    shell: str | bool | None = None
    cleanup_cmd: str | None = None

    @classmethod
    def from_config(cls, config, **context):
        field_names = (field.name.replace("_", "-") for field in fields(cls))
        values = {
            name.replace("-", "_"): config[name]
            for name in field_names
            if name in config
        }
        return cls(**(config_subst(values, **context) if context else values))

    @property
    def has_startup(self):
        return bool((self.cmd_file or "").strip() or (self.cmd or "").strip())


@dataclass
class CmdProcess:
    """Local startup subprocess and its completion information."""

    proc: asyncio.subprocess.Process
    stage_number: int
    pid: int | None = None
    task: asyncio.Task | None = None
    returncode: int | None = None


@dataclass
class StageState:
    """Progress and subprocess association for one stage."""

    stage: LifecycleStage
    number: int
    entered: bool = False
    ready: bool = False
    process: CmdProcess | None = None


def resolve_lifecycle(node, kind, merged, **context):
    """Extract ordered stages from the node and kind configuration.

    The merged configuration already has the node substitutions applied.
    """
    if "commands" in kind.get("merge", []):
        stages = [
            LifecycleStage.from_config(source, **context) for source in (kind, node)
        ]
    else:
        stages = [LifecycleStage.from_config(merged)]
    return stages

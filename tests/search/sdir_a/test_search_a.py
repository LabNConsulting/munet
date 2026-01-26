# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# December 19 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#

"Testing configuration file format variations."

import pytest

from munet import Commander

commander = Commander("base")


@pytest.fixture(name="stdargs")
def fixture_stdargs(rundir):
    a = [
        "uv",
        "run",
        "munet",
        f"--rundir={rundir}",
    ]
    return a


async def test_check_cli(stdargs):
    """Test loading kind configs and proper merging"""
    repl = await commander.shell_spawn(stdargs, "munet>", use_pty=True, is_bourne=False)
    output = repl.cmd_nostatus("help")
    assert "a-example-command" in output
    assert "c-example-command" in output
    assert "z-example-command" in output
    assert "testa-example-command" in output

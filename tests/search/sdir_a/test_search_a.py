# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 19 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; see the file COPYING; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#

"Testing configuration file format variations."
import pytest

from munet import Commander


commander = Commander("base")


@pytest.fixture(name="stdargs")
def fixture_stdargs(rundir):
    a = [
        "poetry",
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

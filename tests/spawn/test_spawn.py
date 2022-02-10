# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# February 12 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
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
# import asyncio
import logging
import os
import time

import pytest


# from munet.parser import build_topology

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def _test_repl(unet, cmd, use_pty):
    r1 = unet.hosts["r1"]
    time.sleep(1)
    repl = await r1.console(cmd, user="root", use_pty=use_pty, trace=True)
    return repl


# XXX dash "STOPPED"s when this is run!?
# @pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/dash", "/bin/sh", "/bin/ksh"])
@pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/ksh"])
async def test_spawn_namespace_piped(unet, shellcmd):
    if not os.path.exists(shellcmd):
        pytest.skip("{} not installed skipping".format(shellcmd))

    repl = await _test_repl(unet, [shellcmd, "-si"], use_pty=False)
    output = repl.run_command("env")
    logging.info("'env' output: %s", output)
    output = repl.run_command("ls /sys")
    logging.info("'ls /sys' output: %s", output)
    output = repl.run_command("echo $?")
    logging.info("'echo $?' output: %s", output)


@pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/dash", "/bin/sh", "/bin/ksh"])
async def test_spawn_namespace_pty(unet, shellcmd):
    if not os.path.exists(shellcmd):
        pytest.skip("{} not installed skipping".format(shellcmd))

    repl = await _test_repl(unet, [shellcmd], use_pty=True)
    output = repl.run_command("env")
    logging.info("'env' output: %s", output)
    output = repl.run_command("ls /")
    logging.info("'ls /' output: %s", output)
    output = repl.run_command("echo $?")
    logging.info("'echo $?' output: %s", output)

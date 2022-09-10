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
"Testing use of pexect/REPL in munet."
import logging
import os
import time

import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def _test_repl(unet, hostname, cmd, use_pty):
    host = unet.hosts[hostname]
    time.sleep(1)
    repl = await host.console(cmd, user="root", use_pty=use_pty, trace=True)
    return repl


@pytest.mark.parametrize("host", ["r1", "r2"])
@pytest.mark.parametrize("mode", ["pty", "piped"])
@pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/dash", "/bin/ksh"])
async def test_spawn(unet, host, mode, shellcmd):
    if not os.path.exists(shellcmd):
        pytest.skip(f"{shellcmd} not installed skipping")

    if mode == "pty":
        repl = await _test_repl(unet, host, [shellcmd], use_pty=True)
    else:
        repl = await _test_repl(unet, host, [shellcmd, "-si"], use_pty=False)

    try:
        output = repl.cmd_raises("unset HISTFILE")
        assert not output.strip()

        os.environ["TEST_SHELL"] = shellcmd
        output = repl.cmd_raises("env | grep TEST_SHELL")
        logging.info("'env | grep TEST_SHELL' output: %s", output)
        assert output == f"SHELL={shellcmd}"

        expected = (
            "block\nbus\nclass\ndev\ndevices\nfirmware\nfs\nkernel\nmodule\npower\n"
        )
        rc, output = repl.cmd_status("ls -1 /sys")
        output = ouptut.replace("hypervisor\n", "")
        logging.info("'ls -1 /sys' rc: %s output: %s", rc, output)
        assert output == expected

        if shellcmd == "/bin/bash":
            output = repl.cmd_raises("!!")
            logging.info("'!!' output: %s", output)
    finally:
        # this is required for setns() restoration to work for non-pty (piped) bash
        if mode != "pty":
            repl.child.proc.kill()

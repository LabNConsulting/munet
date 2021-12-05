# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
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
import asyncio
import io
import logging
import re

import pytest

from munet import Commander
from munet import cli
from munet import cmd_error
from munet.__main__ import main


# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_containers_up(unet):
    output = unet.cmd_raises("podman ps")
    logging.info("Containers:\n%s\n\n", output)


async def check(p, cli_input, cli_output):
    o, e = await p.communicate(cli_input)
    rc = await p.wait()
    o = o.decode("utf-8") if o else o
    e = e.decode("utf-8") if e else e
    s = cmd_error(rc, o, e)
    if rc:
        logging.error("Failed: %s", s)
    assert not rc, s
    assert re.search(cli_output, o)
    logging.info("Success: %s with output: %s", s, o)


async def test_sh_cmd(unet):
    match = r"""------ Host: r1 ------
cmd.err
------- End: r1 ------
------ Host: r2 ------
*** non-zero exit status: 2
ls: cannot access 'cmd.err': No such file or directory
------- End: r2 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "sh ls cmd.err\n", stdout)
    assert match.strip() == stdout.getvalue().strip()

    match = r"cmd.err"
    stdout = io.StringIO()
    assert await cli.doline(unet, "sh r1 ls cmd.err\n", stdout)
    assert match.strip() == stdout.getvalue().strip()

    match = "Filesystem\noverlay"
    stdout = io.StringIO()
    assert await cli.doline(unet, "sh r2 df --output=source /\n", stdout)
    assert match == stdout.getvalue().strip()


async def test_shi_cmd(unet):
    match = r"""------ Host: r1 ------
cmd.err
------- End: r1 ------
------ Host: r2 ------
ls: cannot access 'cmd.err': No such file or directory
------- End: r2 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "shi ls cmd.err\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert match.strip() == value

    match = r"cmd.err"
    stdout = io.StringIO()
    assert await cli.doline(unet, "shi r1 ls cmd.err\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert match.strip() == value

    match = "Filesystem\noverlay"
    stdout = io.StringIO()
    assert await cli.doline(unet, "shi r2 df --output=source /\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert match.strip() == value


async def test_default_cmd(unet):
    match = r"""------ Host: r1 ------
instance:0 name:r1 echo:testing echoback
------- End: r1 ------
------ Host: r2 ------
instance:0 name:r2 echo:testing echoback
------- End: r2 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "testing echoback\n", stdout)
    assert match.strip() == stdout.getvalue().strip()

    match = r"instance:0 name:r1 echo:foo"
    stdout = io.StringIO()
    assert await cli.doline(unet, f"r1 foo\n", stdout)
    assert match.strip() == stdout.getvalue().strip()

    match = r"instance:0 name:r2 echo:bar"
    stdout = io.StringIO()
    assert await cli.doline(unet, f"r2 bar\n", stdout)
    assert match.strip() == stdout.getvalue().strip()


async def test_ls_cmd(unet):
    match = r"cmd.err"
    stdout = io.StringIO()
    assert await cli.doline(unet, f"ls r1 cmd.err\n", stdout)
    assert match.strip() == stdout.getvalue().strip()
    # assert re.match(match, stdout.getvalue().strip())

    match = r"/bin/bash"
    stdout = io.StringIO()
    assert await cli.doline(unet, f"ls r2 /bin/bash\n", stdout)
    # assert re.match(match, stdout.getvalue().strip())
    assert match.strip() == stdout.getvalue().strip()


async def _test_async_cli(unet):
    await cli.async_cli(unet)

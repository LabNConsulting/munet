# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing CLI configuration and use."

import io
import logging
import re
import sys

import pytest

from munet import cli
from munet import cmd_error

# All tests are coroutines
pytestmark = pytest.mark.asyncio

# How does this double assignment work, what's going on?
pytestmark = pytest.mark.parametrize("unet", [True, False], indirect=["unet"])


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
------- End: r2 ------
------ Host: r3 ------
*** non-zero exit status: 2
ls: cannot access 'cmd.err': No such file or directory
------- End: r3 ------"""

    stdout = io.StringIO()
    assert await cli.doline(unet, "sh ls cmd.err\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"""------ Host: r1 ------
ok
------- End: r1 ------
------ Host: r2 ------
ok
------- End: r2 ------
------ Host: r3 ------
ok
------- End: r3 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "sh [[ -t 1 ]] || echo ok\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert value == match.strip()

    match = r"cmd.err"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r1 sh ls cmd.err\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = "Filesystem\noverlay"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r2 sh df --output=source /\n", stdout)
    assert stdout.getvalue().strip() == match

    match = "Filesystem\ntmpfs"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r3 sh df --output=source /var/run\n", stdout)
    assert stdout.getvalue().strip() == match


async def test_shi_cmd(unet):
    if not sys.stdin.isatty():
        pytest.skip("Can't test shell-interactive commands without TTY")

    match = r"cmd.err"
    stdout = io.StringIO()

    assert await cli.doline(unet, "r1 shi ls cmd.err\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert value == match.strip()

    match = "Filesystem\noverlay"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r2 shi df --output=source /\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert value == match.strip()

    match = "Filesystem\ntmpfs"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r3 shi df --output=source /var/run\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert value == match.strip()

    match = r"""------ Host: r1 ------
cmd.err
------- End: r1 ------
------ Host: r2 ------
ls: cannot access 'cmd.err': No such file or directory
------- End: r2 ------
------ Host: r3 ------
ls: cannot access 'cmd.err': No such file or directory
------- End: r3 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "shi ls cmd.err\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert value == match.strip()

    match = r"""------ Host: r1 ------
ok
------- End: r1 ------
------ Host: r2 ------
ok
------- End: r2 ------
------ Host: r3 ------
ok
------- End: r3 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "shi [[ -t 1 ]] && echo ok\n", stdout)
    value = stdout.getvalue().strip().replace("\r", "")
    assert value == match.strip()


async def test_default_cmd(unet):
    match = r"""------ Host: r1 ------
name:r1 echo:testing echoback
------- End: r1 ------
------ Host: r2 ------
name:r2 echo:testing echoback
------- End: r2 ------
------ Host: r3 ------
name:r3 echo:testing echoback
------- End: r3 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "testing echoback\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"name:r1 echo:foo"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r1 foo\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"name:r2 echo:bar"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r2 bar\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"name:r3 echo:bar"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r3 bar\n", stdout)
    assert stdout.getvalue().strip() == match.strip()


async def test_ls_cmd(unet):
    match = r"cmd.err"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r1 ls cmd.err\n", stdout)
    assert stdout.getvalue().strip() == match.strip()
    # assert re.match(match, stdout.getvalue().strip())

    match = r"/bin/bash"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r2 ls /bin/bash\n", stdout)
    # assert re.match(match, stdout.getvalue().strip())
    assert stdout.getvalue().strip() == match.strip()

    match = r"/bin/bash"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r3 ls /bin/bash\n", stdout)
    # assert re.match(match, stdout.getvalue().strip())
    assert stdout.getvalue().strip() == match.strip()


async def test_fstring(unet):
    match = r"HOSTNAME is r1"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r1 hostname\n", stdout)
    assert stdout.getvalue().strip() == match.strip()
    # assert re.match(match, stdout.getvalue().strip())

    # match = r"/bin/bash"
    # stdout = io.StringIO()
    # assert await cli.doline(unet, "r2 ls /bin/bash\n", stdout)
    # # assert re.match(match, stdout.getvalue().strip())
    # assert stdout.getvalue().strip() == match.strip()


async def test_toplevel_no_host(unet):
    netname = "net0"
    stdout = io.StringIO()
    assert await cli.doline(unet, f"toplevel-ip link show {netname}\n", stdout)
    assert re.match(rf"\d+: {netname}: <.*> mtu 1500.*", stdout.getvalue())

    netname = "nonet0"
    stdout = io.StringIO()
    assert await cli.doline(unet, f"toplevel-ip link show {netname}\n", stdout)
    assert not re.match(rf"\d+: {netname}: <.*> mtu 1500.*", stdout.getvalue())


async def test_toplevel_host(unet):
    match = r"""------ Host: r1 ------
name:r1 echo:testing echoback
------- End: r1 ------
------ Host: r2 ------
name:r2 echo:testing echoback
------- End: r2 ------
------ Host: r3 ------
name:r3 echo:testing echoback
------- End: r3 ------"""
    stdout = io.StringIO()
    assert await cli.doline(unet, "toplevel-echo testing echoback\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    stdout = io.StringIO()
    assert await cli.doline(unet, "r1 r2 r3 toplevel-echo testing echoback\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"name:r1 echo:foo"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r1 toplevel-echo foo\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"name:r2 echo:bar"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r2 toplevel-echo bar\n", stdout)
    assert stdout.getvalue().strip() == match.strip()

    match = r"name:r3 echo:bar"
    stdout = io.StringIO()
    assert await cli.doline(unet, "r3 toplevel-echo bar\n", stdout)
    assert stdout.getvalue().strip() == match.strip()


async def _test_async_cli(unet, rundir):
    await cli.async_cli(unet, histfile=f"{rundir}/cli-histfile.txt")

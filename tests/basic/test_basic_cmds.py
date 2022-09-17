# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# September 17 2022, Christian Hopps <chopps@labn.net>
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
"Testing of basic topology configuration."
import subprocess

import pytest

# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_cmd_raises(unet):
    r1 = unet.hosts["r1"]

    o = r1.cmd_raises("echo Foobar")
    assert o == "Foobar\n"

    try:
        r1.cmd_raises("ls ajfipoasdjiopa", warn=False)
    except subprocess.CalledProcessError as error:
        assert error.returncode == 2
        assert "No such file or directory" in error.stderr
    else:
        assert False, "Failed to raise error"

    try:
        await r1.async_cmd_raises("ls ajfipoasdjiopa", warn=False)
    except subprocess.CalledProcessError as error:
        assert error.returncode == 2
        assert "No such file or directory" in error.stderr
    else:
        assert False, "Failed to raise error"


async def test_cmd_status(unet):
    r1 = unet.hosts["r1"]

    rc, o, e = r1.cmd_status("echo Foobar")
    assert o == "Foobar\n"
    assert e == ""
    assert rc == 0

    rc, o, e = r1.cmd_status("ls ajfipoasdjiopa", warn=False)
    assert rc == 2
    assert "No such file or directory" in e
    assert o == ""

    rc, o, e = await r1.async_cmd_status("echo Foobar")
    assert o == "Foobar\n"
    assert e == ""
    assert rc == 0

    rc, o, e = await r1.async_cmd_status("ls ajfipoasdjiopa", warn=False)
    assert rc == 2
    assert "No such file or directory" in e
    assert o == ""


async def test_cmd_nostatus(unet):
    r1 = unet.hosts["r1"]

    o = r1.cmd_nostatus("echo Foobar")
    assert o == "Foobar\n"

    o = r1.cmd_nostatus("echo Foobar", stderr=subprocess.STDOUT)
    assert o == "Foobar\n"

    o, e = r1.cmd_nostatus("echo Foobar", stderr=subprocess.PIPE)
    assert o == "Foobar\n"
    assert e == ""

    o = await r1.async_cmd_nostatus("echo Foobar")
    assert o == "Foobar\n"

    o = await r1.async_cmd_nostatus("echo Foobar", stderr=subprocess.STDOUT)
    assert o == "Foobar\n"

    o, e = await r1.async_cmd_nostatus("echo Foobar", stderr=subprocess.PIPE)
    assert o == "Foobar\n"
    assert e == ""


async def test_popen(unet):
    r1 = unet.hosts["r1"]

    p = r1.popen("echo Foobar")
    o, e = p.communicate()
    rc = p.wait()
    assert rc == 0
    assert o == "Foobar\n"
    assert e == ""

    # XXX should really test this with real async actions
    p = await r1.async_popen(["echo", "Foobar"])
    o, e = await p.communicate()
    rc = await p.wait()
    assert rc == 0
    assert o == b"Foobar\n"
    assert e == b""

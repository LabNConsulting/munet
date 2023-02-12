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
import asyncio
import os
import subprocess

import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio

# How does this double assignment work, what's going on?
pytestmark = pytest.mark.parametrize("unet", [True, False], indirect=["unet"])


async def wait_remote_up(unet):
    rnode = unet.hosts["sshsrv"]
    t = rnode.rundir.joinpath("started")
    for _ in range(0, 50):
        if t.exists():
            return
        await asyncio.sleep(0.1)
    assert False, "took more than 5 seconds to bring up sshd server"


@pytest.mark.parametrize("host", ["host1", "container1", "remote1"])
async def test_cmd_raises(unet, host):
    if host == "remote1":
        await wait_remote_up(unet)
    host = unet.hosts[host]

    o = host.cmd_raises("echo Foobar")
    assert o == "Foobar\n"

    try:
        host.cmd_raises("ls ajfipoasdjiopa", warn=False)
    except subprocess.CalledProcessError as error:
        assert error.returncode == 2
        assert "No such file or directory" in error.stderr
    else:
        assert False, "Failed to raise error"

    try:
        await host.async_cmd_raises("ls ajfipoasdjiopa", warn=False)
    except subprocess.CalledProcessError as error:
        assert error.returncode == 2
        assert "No such file or directory" in error.stderr
    else:
        assert False, "Failed to raise error"


@pytest.mark.parametrize("host", ["host1", "container1", "remote1"])
async def test_cmd_status(unet, host):
    if host == "remote1":
        await wait_remote_up(unet)
    host = unet.hosts[host]

    rc, o, e = host.cmd_status("echo Foobar")
    assert o == "Foobar\n"
    assert e == ""
    assert rc == 0

    rc, o, e = host.cmd_status("ls ajfipoasdjiopa", warn=False)
    assert rc == 2, f"o: {o}\n" + f"e: {e}\n"
    assert o == ""
    assert "No such file or directory" in e

    rc, o, e = await host.async_cmd_status("echo Foobar")
    assert o == "Foobar\n"
    assert e == ""
    assert rc == 0

    rc, o, e = await host.async_cmd_status("ls ajfipoasdjiopa", warn=False)
    assert rc == 2
    assert "No such file or directory" in e
    assert o == ""


@pytest.mark.parametrize("host", ["host1", "container1", "remote1"])
async def test_cmd_nostatus(unet, host):
    if host == "remote1":
        await wait_remote_up(unet)
    host = unet.hosts[host]

    o = host.cmd_nostatus("echo Foobar")
    assert o == "Foobar\n"

    o = host.cmd_nostatus("echo Foobar", stderr=subprocess.STDOUT)
    assert o == "Foobar\n"

    o, e = host.cmd_nostatus("echo Foobar", stderr=subprocess.PIPE)
    assert o == "Foobar\n"
    assert e == ""

    o = host.cmd_nostatus("ls ajfipoasdjiopa", warn=False)
    assert "No such file or directory" in o

    o, e = host.cmd_nostatus("ls ajfipoasdjiopa", warn=False, stderr=subprocess.PIPE)
    assert o == ""
    assert "No such file or directory" in e

    o = await host.async_cmd_nostatus("echo Foobar")
    assert o == "Foobar\n"

    o = await host.async_cmd_nostatus("echo Foobar", stderr=subprocess.STDOUT)
    assert o == "Foobar\n"

    o, e = await host.async_cmd_nostatus("echo Foobar", stderr=subprocess.PIPE)
    assert o == "Foobar\n"
    assert e == ""

    o = await host.async_cmd_nostatus("ls ajfipoasdjiopa", warn=False)
    assert "No such file or directory" in o

    o, e = await host.async_cmd_nostatus(
        "ls ajfipoasdjiopa", warn=False, stderr=subprocess.PIPE
    )
    assert o == ""
    assert "No such file or directory" in e


@pytest.mark.parametrize("host", ["host1", "container1", "remote1"])
async def test_popen(unet, host):
    if host == "remote1":
        await wait_remote_up(unet)
    host = unet.hosts[host]

    p = host.popen("echo Foobar")
    o, e = p.communicate()
    rc = p.wait()
    assert e == ""
    assert rc == 0
    assert o == "Foobar\n"

    # XXX should really test this with real async actions
    p = await host.async_popen(["echo", "Foobar"])
    o, e = await p.communicate()
    rc = await p.wait()
    assert rc == 0
    assert o == b"Foobar\n"
    assert e == b""

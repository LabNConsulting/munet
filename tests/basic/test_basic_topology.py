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
import logging

import pytest

from micronet.parser import build_topology


# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def test_basic_ping(unet):
    other_ip = unet.hosts["r2"].intf_addrs["eth0"].ip
    o = await unet.hosts["r1"].async_cmd_raises(f"ping -w1 -c1 {other_ip}")
    logging.info("ping r2 output: %s", o)

    # useful for manually testing the CLI
    # from micronet.cli import async_cli
    # await async_cli(unet, title="First", prompt="primary> ")

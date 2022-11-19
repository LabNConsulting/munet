# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# September 13 2022, Christian Hopps <chopps@labn.net>
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
"Tests of L3Qemu node type"
import logging

import pytest

from common.fetch import fetch


# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True, scope="module")
async def fetch_images():
    assets = ["bzImage", "rootfs.cpio.gz"]
    fetch("LabNConsulting", "iptfs-dev", assets)


async def test_qemu_up(unet):
    r1 = unet.hosts["r1"]
    output = r1.monrepl.cmd_nostatus("info status")
    logging.debug("r1: kvm status: %s", output)

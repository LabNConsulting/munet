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
import requests


# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True, scope="module")
async def fetch_images():
    assets = ["bzImage", "rootfs.cpio.gz"]

    bheader = {"Accept": "application/octet-stream"}
    api = "https://api.github.com/repos"
    owner = "LabNConsulting"
    repo = "iptfs-dev"
    qurl = f"{api}/{owner}/{repo}/releases/latest"
    latest_json = requests.get(qurl, timeout=30).json()

    for asset in latest_json["assets"]:
        # for curl if we wanted ot use that
        # burl = asset["browser_download_url"]
        name = asset["name"]
        if name not in assets:
            logging.warning("Skipping unknown asset '%s'", name)
        aid = asset["id"]
        aurl = f"{api}/{owner}/{repo}/releases/assets/{aid}"
        logging.info("Downloading asset '%s'", name)
        rfile = requests.get(aurl, headers=bheader, timeout=600)
        open(name, "wb+").write(rfile.content)


async def test_qemu_up(unet):
    r1 = unet.hosts["r1"]
    output = r1.monrepl.cmd_nostatus("info status")
    logging.debug("r1: kvm status: %s", output)

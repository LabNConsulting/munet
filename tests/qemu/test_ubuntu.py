# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 13 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
#
"Tests of L3Qemu node type"

import logging
import os

import pytest

from munet.base import commander

# All tests are coroutines
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize("unet", ["munet-vm"], indirect=["unet"]),
]


@pytest.fixture(autouse=True, scope="module")
async def setup_images(rundir_module):
    try:
        rdir = rundir_module
        release = "22.04"
        # This is actually a qcow2 image regardless of the .img suffix
        bimage = f"ubuntu-{release}-server-cloudimg-amd64.img"
        image_url = (
            f"https://cloud-images.ubuntu.com/releases/{release}/release/{bimage}"
        )
        qimage = "ubuntu-tpl.qcow2"

        if not os.path.exists(bimage):
            commander.cmd_raises(f"curl -fLO {image_url}")

        if not os.path.exists(qimage):
            commander.cmd_raises(f"rm -f {qimage} && ln -sf {bimage} {qimage}")

        if not os.path.exists(f"{rdir}/root-key"):
            commander.cmd_raises(
                f'ssh-keygen -b 2048 -t rsa -f {rdir}/root-key -q -N ""'
            )
        pubkey = commander.cmd_raises(f"cat {rdir}/root-key.pub").strip()
        user_data = f"""#cloud-config
disable_root: 0
ssh_pwauth: 1
users:
  - name: root
    lock_passwd: false
    plain_text_passwd: foobar
    ssh_authorized_keys:
      - "{pubkey}"
hostname: r1
runcmd:
  - systemctl enable serial-getty@ttyS1.service
  - systemctl start serial-getty@ttyS1.service
  - systemctl enable serial-getty@ttyS2.service
  - systemctl start serial-getty@ttyS2.service
"""
        commander.cmd_raises(f"cat > {rdir}/user-data.yaml", stdin=user_data)
        commander.cmd_raises(
            "cloud-localds -N netcfg.yaml -d raw"
            f" {rdir}/r1-seed.img {rdir}/user-data.yaml"
        )
    except Exception:
        pytest.fail("Failed to fetch/setup qemu images")


async def test_qemu_up(unet):
    r1 = unet.hosts["r1"]
    output = r1.monrepl.cmd_nostatus("info status")
    assert output == "VM status: running"


async def test_net_up(unet):
    h1 = unet.hosts["h1"]
    r1 = unet.hosts["r1"]

    h1mgmt0ip = h1.get_intf_addr("eth0").ip
    r1mgmt0ip = r1.get_intf_addr("eth0").ip

    h1r1ip = h1.get_intf_addr("eth1").ip
    r1h1ip = r1.get_intf_addr("eth1").ip

    logging.debug(h1.cmd_raises("ping -w1 -c1 192.168.0.254"))
    logging.debug(h1.cmd_raises(f"ping -w1 -c1 {r1mgmt0ip}"))
    logging.debug(h1.cmd_raises(f"ping -w1 -c1 {r1h1ip}"))

    # Convert to SSH when we download the root-key artifact
    # logging.debug(r1.conrepl.cmd_raises("ping -w1 -c1 192.168.0.254"))
    # logging.debug(r1.conrepl.cmd_raises(f"ping -w1 -c1 {h1mgmt0ip}"))
    # logging.debug(r1.conrepl.cmd_raises(f"ping -w1 -c1 {h1r1ip}"))
    logging.debug(r1.cmd_raises("ping -w1 -c1 192.168.0.254"))
    logging.debug(r1.cmd_raises(f"ping -w1 -c1 {h1mgmt0ip}"))
    logging.debug(r1.cmd_raises(f"ping -w1 -c1 {h1r1ip}"))

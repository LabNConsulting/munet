# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# June 6 2025, Liam Brady <lbrady@labn.net>
#
# Copyright 2025, LabN Consulting, L.L.C.
#
"Tests of initial-cmd-file and cmd-file config for L3QemuNode"

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
        existing_disk = f"{rdir}/existing.qcow2"
        if not os.path.exists(existing_disk):
            template = os.path.abspath(qimage)
            commander.cmd_raises(
                f"qemu-img create -f qcow2 -F qcow2 -b {template} {existing_disk}"
            )

        for node in ["r1", "r2", "existing-disk"]:
            user_data = f"""#cloud-config
disable_root: 0
ssh_pwauth: 1
users:
  - name: root
    lock_passwd: false
    plain_text_passwd: foobar
    ssh_authorized_keys:
      - "{pubkey}"
hostname: {node}
runcmd:
  - systemctl enable serial-getty@ttyS1.service
  - systemctl start serial-getty@ttyS1.service
  - systemctl enable serial-getty@ttyS2.service
  - systemctl start serial-getty@ttyS2.service
"""
            commander.cmd_raises(f"cat > {rdir}/{node}-user-data.yaml", stdin=user_data)
            network = "" if node == "existing-disk" else f"-N {node}-netcfg.yaml "
            commander.cmd_raises(
                f"cloud-localds {network}-d raw"
                f" {rdir}/{node}-config-cmd.img {rdir}/{node}-user-data.yaml"
            )
    except Exception:
        pytest.fail("Failed to fetch/setup qemu images")


async def test_qemu_up(unet):
    r1 = unet.hosts["r1"]
    output = r1.monrepl.cmd_nostatus("info status")
    assert output == "VM status: running"
    r2 = unet.hosts["r2"]
    output = r2.monrepl.cmd_nostatus("info status")
    assert output == "VM status: running"


async def test_config_cmd(unet):
    r1 = unet.hosts["r1"]
    r2 = unet.hosts["r2"]

    output = r1.conrepl.cmd_raises("ls")
    logging.debug(output)
    assert "foo" in output  # from cmd-file
    assert "bar" in output  # from initial-cmd-file

    output = r2.conrepl.cmd_raises("ls")
    logging.debug(output)
    assert "foo" in output  # from cmd
    assert "bar" in output  # from initial-cmd


async def test_composed_qemu_cleanup(unet):
    r1 = unet.hosts["r1"]
    assert r1.cmdrepl is not None
    r1.conrepl.cmd_raises("test -f /root/kind-ready -a ! -f /root/ignored-initializer")
    await r1.async_cleanup_cmd()
    assert r1.conrepl.cmd_raises("cat /root/cleanup-order") == "node\nkind"
    assert r1.monrepl.cmd_nostatus("info status") == "VM status: running"


async def test_primary_console_and_existing_disk(unet):
    r2 = unet.hosts["r2"]
    assert r2.cmdrepl is None
    r2.conrepl.cmd_raises("test -f /root/foo -a -f /root/bar")
    await r2.async_cleanup_cmd()
    assert r2.conrepl.cmd_raises("cat /root/direct-cleanup") == "node argument"

    vm = unet.hosts["existing-disk"]
    assert vm.cmdrepl is None
    vm.conrepl.cmd_raises("test ! -f /root/unexpected-initializer")

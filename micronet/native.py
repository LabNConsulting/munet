# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# October 1 2021, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 1, LabN Consulting, L.L.C.
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
import ipaddress
import logging
import os
import signal
import subprocess
import tempfile

from .base import BaseMicronet
from .base import Bridge
from .base import LinuxNamespace


def get_ip_interface(c):
    if "ip" in c and c["ip"] != "auto":
        return ipaddress.ip_interface(c["ip"])
    return None


def get_ip_network(c):
    if "ip" in c and c["ip"] != "auto":
        return ipaddress.ip_network(c["ip"])
    return None


def make_ip_network(net, inc):
    n = ipaddress.ip_network(net)
    return ipaddress.ip_network(
        (n.network_address + inc * n.num_addresses, n.prefixlen)
    )


async def to_thread(func):
    """to_thread for python < 3.9"""
    try:
        return await asyncio.to_thread(func)
    except AttributeError:
        logging.warning("Using backport to_thread")
        return await asyncio.get_running_loop().run_in_executor(None, func)


class L3Bridge(Bridge):
    """
    A linux bridge.
    """

    def __init__(self, name=None, unet=None, logger=None, config=None):
        """Create a linux Bridge."""

        self.unet = unet
        super().__init__(name, unet=unet, logger=logger)

        self.config = config if config else {}
        ip = get_ip_network(self.config)
        self.ip = ip if ip else make_ip_network("10.0.0.0/24", self.id)
        self.cmd_raises(f"ip addr add {self.ip} dev {name}")
        self.logger.debug("%s: set network address to %s", self, self.ip)


class L3Node(LinuxNamespace):
    next_ord = 1

    @classmethod
    def _get_next_ord(cls):
        n = cls.next_ord
        cls.next_ord = n + 1
        return n

    def __init__(self, name=None, logger=None, unet=None, config=None, **kwargs):
        """Create a linux Bridge."""

        self.id = self._get_next_ord()
        if not name:
            name = "r{}".format(self.id)

        super().__init__(name, logger=logger, **kwargs)

        self.cmd_p = None
        self.config = config if config else {}

        # Setup node's networking
        if ip := get_ip_interface(self.config):
            self.loopback_ip = ipaddress.ip_interface(ip)
        else:
            self.loopback_ip = ipaddress.ip_interface("10.255.0.0/32") + self.id
        self.ip = self.loopback_ip.ip
        self.next_p2p_network = ipaddress.ip_network(f"10.254.{self.id}.0/31")
        self.unet = unet

        self.cmd_raises(f"ip addr add {self.loopback_ip} dev lo")
        self.cmd_raises("ip link set lo up")

        # Create rundir and arrange for future commands to run in it.
        self.rundir = os.path.join(unet.rundir, name)
        self.cmd_raises(f"mkdir -p {self.rundir}")
        self.set_cwd(self.rundir)

        self.logger.debug("%s: node ip address %s", self, self.ip)

    async def run_cmd(self):
        """Run the configured commands for this node"""
        cmd = self.config.get("cmd", "").strip()
        if not cmd:
            return None
        if cmd.find("\n") == -1:
            cmd += "\n"

        cmdpath = os.path.join(self.rundir, "cmd.txt")
        with open(cmdpath, mode="w+", encoding="utf-8") as cmdfile:
            cmdfile.write(cmd)
            cmdfile.flush()

        bash_path = self.get_exec_path("bash")
        cmds = [bash_path, cmdfile.name]
        self.cmd_p = await self.async_popen(
            cmds,
            stdin=subprocess.DEVNULL,
            stdout=open(os.path.join(self.rundir, "cmd.out"), "wb"),
            stderr=open(os.path.join(self.rundir, "cmd.err"), "wb"),
            # start_new_session=True,  # allows us to signal all children to exit
        )
        self.logger.debug(
            "%s: popen %s => %s",
            self,
            cmds,
            self.cmd_p.pid,
        )
        return self.cmd_p

    def set_lan_addr(self, ifname, switch):

        self.logger.debug(
            "%s: prefixlen of switch %s is %s", self, switch.name, switch.ip.prefixlen
        )
        ipaddr = ipaddress.ip_interface(
            (switch.ip.network_address + self.id, switch.ip.prefixlen)
        )
        self.intf_addrs[ifname] = ipaddr
        self.logger.debug("%s: adding %s to lan intf %s", self, ipaddr, ifname)
        self.intf_ip_cmd(ifname, f"ip addr add {ipaddr} dev {ifname}")

    def set_p2p_addr(self, ifname, other, oifname):
        n = self.next_p2p_network
        self.next_p2p_network = make_ip_network(n, 1)

        ipaddr = ipaddress.ip_interface(n)
        oipaddr = ipaddr + 1

        self.intf_addrs[ifname] = ipaddr
        other.intf_addrs[oifname] = oipaddr

        self.logger.debug("%s: adding %s to p2p intf %s", self, ipaddr, ifname)
        self.intf_ip_cmd(ifname, f"ip addr add {ipaddr} dev {ifname}")
        self.logger.debug("%s: adding %s to other p2p intf %s", other, oipaddr, oifname)
        other.intf_ip_cmd(oifname, f"ip addr add {oipaddr} dev {oifname}")

    def delete(self):
        self.cleanup_proc(self.cmd_p)
        super().delete()


class Micronet(BaseMicronet):
    """
    Micronet.
    """

    def __init__(self, rundir=None, **kwargs):
        super().__init__(**kwargs)
        self.rundir = rundir if rundir else tempfile.mkdtemp(prefix="unet")
        self.cmd_raises(f"mkdir -p {self.rundir} && chmod 755 {self.rundir}")

    def add_l3_link(self, node1, node2, c1, c2):
        """Add a link between switch and node or 2 nodes."""
        isp2p = False

        if node1.name in self.switches:
            assert node2.name in self.hosts
        elif node2.name in self.switches:
            assert node1.name in self.hosts
            node1, node2 = node2, node1
            c1, c2 = c2, c1
        else:
            # p2p link
            assert node1.name in self.hosts
            assert node1.name in self.hosts
            isp2p = True

        if1 = c1["name"] if "name" in c1 else node1.get_next_intf_name()
        if2 = c2["name"] if "name" in c2 else node2.get_next_intf_name()

        super().add_link(node1, node2, if1, if2)

        if isp2p:
            node1.set_p2p_addr(if1, node2, if2)
        else:
            node2.set_lan_addr(if2, node1)

    def add_l3_node(self, name, config, **kwargs):
        """Add a node to micronet."""

        return super().add_host(name, cls=L3Node, unet=self, config=config, **kwargs)

    def add_l3_switch(self, name, config, **kwargs):
        """Add a switch to micronet."""

        return super().add_switch(name, cls=L3Bridge, config=config, **kwargs)

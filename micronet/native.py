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
import ipaddress

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
    return ipaddress.ip_network((n.network_address + n.num_addresses, n.prefixlen))


class L3Bridge(Bridge):
    """
    A linux bridge.
    """

    def __init__(self, name=None, unet=None, logger=None, config=None):
        """Create a linux Bridge."""

        super().__init__(name, unet, logger)

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

    def __init__(self, name=None, logger=None, config=None, **kwargs):
        """Create a linux Bridge."""

        self.id = self._get_next_ord()
        if not name:
            name = "r{}".format(self.id)
        super().__init__(name, logger=logger, **kwargs)

        self.config = config if config else {}
        ip = get_ip_interface(self.config)
        self.ip = ip if ip else make_ip_network("10.255.0.0/32", self.id)
        self.loopback_ip = self.ip
        self.cmd_raises(f"ip addr add {self.ip} dev lo")
        self.cmd_raises("ip link set lo up")

        self.next_p2p_network = ipaddress.ip_network(f"10.254.{self.id}.0/31")

        self.logger.debug("%s: node ip address %s", self, self.ip)

    def set_lan_addr(self, ifname, switch):

        self.logger.debug(
            "%s: prefixlen of switch %s is %s", self, switch.name, switch.ip.prefixlen
        )
        ipaddr = ipaddress.ip_interface(
            (switch.ip.network_address + self.id, switch.ip.prefixlen)
        )
        self.intf_addrs[ifname] = ipaddr
        self.logger.debug("%s: adding %s to lan intf %s", self, ipaddr, ifname)
        self.intf_ip_cmd(ifname, f"ip addr add {ipaddr} dev {{}}")

    def set_p2p_addr(self, ifname, other, oifname):
        n = self.next_p2p_network
        self.next_p2p_network = make_ip_network(n, 1)

        ipaddr = ipaddress.ip_interface(n)
        oipaddr = ipaddr + 1

        self.intf_addrs[ifname] = ipaddr
        other.intf_addrs[oifname] = oipaddr

        self.logger.debug("%s: adding %s to p2p intf %s", self, ipaddr, ifname)
        self.intf_ip_cmd(ifname, f"ip addr add {ipaddr} dev {{}}")
        self.logger.debug("%s: adding %s to other p2p intf %s", other, oipaddr, oifname)
        other.intf_ip_cmd(oifname, f"ip addr add {oipaddr} dev {{}}")


class Micronet(BaseMicronet):
    """
    Micronet.
    """

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

        return super().add_host(name, cls=L3Node, config=config, **kwargs)

    def add_l3_switch(self, name, config, **kwargs):
        """Add a switch to micronet."""

        return super().add_switch(name, cls=L3Bridge, config=config, **kwargs)

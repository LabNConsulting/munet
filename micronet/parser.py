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
import logging
import os
from copy import deepcopy

from .native import Micronet


def find_matching_net_config(name, cconf, oconf):
    oconnections = oconf.get("connections", None)
    if not oconnections:
        return {}
    match = cconf.get("match", None)
    for conn in oconnections:
        if isinstance(conn, str):
            if conn == name:
                return {}
            continue
        if conn["to"] == name and match == conn.get("match", None):
            return conn
    return None


def get_config(fname):
    if not fname:
        for ext in ("yaml", "toml", "json"):
            if os.path.exists("topology." + ext):
                fname = "topology." + ext
                break
        else:
            raise FileNotFoundError("topology.{json,toml,yaml}")
    _, ext = fname.rsplit(".", 1)
    if ext == "json":
        import json  # pylint: disable=C0415

        logging.info("loading json config from %s/%s", os.getcwd(), fname)
        config = json.load(open(fname, encoding="utf-8"))
    elif ext == "toml":
        import toml  # pylint: disable=C0415

        logging.info("loading toml config from %s/%s", os.getcwd(), fname)
        config = toml.load(fname)
    elif ext == "yaml":
        import yaml  # pylint: disable=C0415

        logging.info("loading yaml config from %s/%s", os.getcwd(), fname)
        config = yaml.safe_load(open(fname, encoding="utf-8"))
    else:
        config = {}
    return config


def build_topology(config=None, logger=None):
    unet = Micronet()

    if not config:
        config = get_config(None)
    if "topology" not in config:
        return unet
    config = config["topology"]

    if "switches" in config:
        for name, swconf in config["switches"].items():
            unet.add_l3_switch(name, deepcopy(swconf), logger=logger)

    if "nodes" in config:
        for name, nconf in config["nodes"].items():
            unet.add_l3_node(name, deepcopy(nconf), logger=logger)

    # Go through all connections and name them so they are sane to the user
    # otherwise when we do p2p links the names/ords skip around based oddly
    for name, node in unet.hosts.items():
        nconf = node.config
        if "connections" not in nconf:
            continue
        nconns = []
        for cconf in nconf["connections"]:
            # Replace string only with a dictionary
            if isinstance(cconf, str):
                cconf = {"to": cconf}
            # Allocate a name if not already assigned
            if "name" not in cconf:
                cconf["name"] = node.get_next_intf_name()
            nconns.append(cconf)
        nconf["connections"] = nconns

    for name, node in unet.hosts.items():
        nconf = node.config
        if "connections" not in nconf:
            continue
        for cconf in nconf["connections"]:
            # Eventually can add support for unconnected intf here.
            if "to" not in cconf:
                continue
            to = cconf["to"]
            if to in unet.switches:
                switch = unet.switches[to]
                swconf = find_matching_net_config(name, cconf, switch.config)
                unet.add_l3_link(switch, node, swconf, cconf)
            elif cconf["name"] not in node.intfs:
                # Only add the p2p interface if not already there.
                other = unet.hosts[to]
                oconf = find_matching_net_config(name, cconf, other.config)
                unet.add_l3_link(node, other, cconf, oconf)

    return unet

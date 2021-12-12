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
import importlib.resources
import json
import logging
import logging.config
import os
import subprocess
import sys
import tempfile

from collections.abc import Iterable
from copy import deepcopy

from . import cli
from .native import Munet


def find_matching_net_config(name, cconf, oconf):
    oconnections = oconf.get("connections", None)
    if not oconnections:
        return {}
    rname = cconf.get("remote-name", None)
    for oconn in oconnections:
        if isinstance(oconn, str):
            if oconn == name:
                return {}
            continue
        if oconn["to"] == name:
            if not rname:
                return oconn
            if rname == oconn.get("name", None):
                return oconn
    return None


def get_config(pathname=None, basename="munet", search=None, logf=logging.debug):
    if not pathname:
        if not search:
            search = [os.getcwd()]
        elif isinstance(search, str):
            search = [search]
        for d in search:
            logf(
                "%s",
                'searching in "{}" for "{}".{{yaml, toml, json}}'.format(d, basename),
            )
            for ext in ("yaml", "toml", "json"):
                pathname = os.path.join(d, basename + "." + ext)
                if os.path.exists(pathname):
                    logf("%s", 'Found "{}"'.format(pathname))
                    break
            else:
                continue
            break
        else:
            raise FileNotFoundError(basename + ".{json,toml,yaml} in " + f"{search}")
    _, ext = pathname.rsplit(".", 1)
    if ext == "json":
        config = json.load(open(pathname, encoding="utf-8"))
    elif ext == "toml":
        import toml  # pylint: disable=C0415

        config = toml.load(pathname)
    elif ext == "yaml":
        import yaml  # pylint: disable=C0415

        config = yaml.safe_load(open(pathname, encoding="utf-8"))
    else:
        raise ValueError("Filename does not end with (.json|.toml|.yaml)")

    config["config_pathname"] = os.path.realpath(pathname)
    return config


def setup_logging(args):
    # Create rundir and arrange for future commands to run in it.

    # Change CWD to the rundir prior to parsing config
    old = os.getcwd()
    os.chdir(args.rundir)
    try:
        search = [old]
        with importlib.resources.path("munet", "logconf.yaml") as datapath:
            search.append(datapath.parent)

        def logf(msg, *p, **k):
            if args.verbose:
                print("PRELOG: " + msg % p, **k, file=sys.stderr)

        config = get_config(args.log_config, "logconf", search, logf=logf)
        pathname = config["config_pathname"]
        del config["config_pathname"]

        if args.verbose:
            config["handlers"]["console"]["level"] = "DEBUG"
        logging.config.dictConfig(config)
        logging.info("Loaded logging config %s", pathname)
    finally:
        os.chdir(old)


def write_hosts_files(unet, netname):
    entries = []
    if netname:
        for name, node in unet.hosts.items():
            ifname = node.get_ifname(netname)
            if ifname in node.intf_addrs:
                entries.append((name, node.intf_addrs[ifname].ip))
    for name, node in unet.hosts.items():
        with open(os.path.join(node.rundir, "hosts.txt"), "w", encoding="ascii") as hf:
            hf.write(
                f"""127.0.0.1\tlocalhost {name}
::1\tip6-localhost ip6-loopback
fe00::0\tip6-localnet
ff00::0\tip6-mcastprefix
ff02::1\tip6-allnodes
ff02::2\tip6-allrouters
"""
            )
            for e in entries:
                hf.write(f"{e[1]}\t{e[0]}\n")


def load_kinds(args):
    # Change CWD to the rundir prior to parsing config
    old = os.getcwd()
    if args:
        os.chdir(args.rundir)

    try:
        search = [old]
        with importlib.resources.path("munet", "kinds.yaml") as datapath:
            search.append(datapath.parent)

        args_config = args.kinds_config if args else None
        config = get_config(args_config, "kinds", search)
        del config["config_pathname"]
        return config["kinds"] if "kinds" in config else {}
    finally:
        if args:
            os.chdir(old)
    return {}


def config_subst(config, **kwargs):
    if isinstance(config, str):
        for name, value in kwargs.items():
            config = config.replace(f"%{name.upper()}%", value)
    elif isinstance(config, Iterable):
        try:
            return {k: config_subst(config[k], **kwargs) for k in config}
        except (KeyError, TypeError):
            return [config_subst(x, **kwargs) for x in config]
    return config


def value_merge_deepcopy(s1, s2):
    "Create a deepcopy of the result of merging the values of keys from dicts d1 and d2"
    d = {}
    for k, v in s1.items():
        if k not in s2:
            d[k] = deepcopy(v)


def merge_kind_config(kconf, config):
    mergekeys = kconf.get("merge", [])
    new = {**kconf}
    for k in new:
        if k not in config:
            continue

        if k not in mergekeys:
            new[k] = config[k]
        elif isinstance(new[k], list):
            new[k].extend(config[k])
        elif isinstance(new[k], dict):
            new[k] = {**new[k], **config[k]}
        else:
            new[k] = config[k]
    for k in config:
        if k not in new:
            new[k] = config[k]
    return new


def build_topology(config=None, logger=None, rundir=None, args=None):
    if not rundir:
        rundir = tempfile.mkdtemp(prefix="unet")
    subprocess.run(f"mkdir -p {rundir} && chmod 755 {rundir}", check=True, shell=True)

    isolated = not args.host if args else True
    unet = Munet(logger=logger, rundir=rundir, isolated=isolated)

    if not config:
        config = get_config(basename="munet")

    if config:
        unet.config = config
        unet.config_pathname = os.path.realpath(config["config_pathname"])
        unet.config_dirname = os.path.dirname(unet.config_pathname)

    if not config or "topology" not in config:
        return unet

    if "cli" in config:
        cli.add_cli_config(unet, config["cli"])

    config = config["topology"]

    kinds = load_kinds(args)
    if "kinds" in config and config["kinds"]:
        kinds = {**kinds, **config["kinds"]}

    # Allow for all networks to be auto-numbered
    autonumber = config.get("networks-autonumber")

    if "networks" in config:
        for name, conf in config["networks"].items():
            if conf is None:
                conf = {}
            kind = conf.get("kind")
            kconf = kinds.get(kind) if kind else None
            if kconf:
                conf = merge_kind_config(kconf, conf)
            conf = config_subst(
                conf, instance=unet.instance, name=name, rundir=unet.rundir
            )
            if "ip" not in conf and autonumber:
                conf["ip"] = "auto"
            config["networks"][name] = conf
            unet.add_network(name, conf, logger=logger)

    if "nodes" in config:
        for name, conf in config["nodes"].items():
            if conf is None:
                conf = {}
            kind = conf.get("kind")
            kconf = kinds.get(kind) if kind else {}
            if kconf:
                conf = merge_kind_config(kconf, conf)
            conf = config_subst(
                conf, instance=unet.instance, name=name, rundir=unet.rundir
            )
            config["nodes"][name] = conf
            unet.add_l3_node(name, conf, logger=logger)

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
                cconf = cconf.split(":", 1)
                cconf = {"to": cconf[0]}
                if len(cconf) == 2:
                    cconf["name"] = cconf[1]
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
                unet.add_native_link(switch, node, swconf, cconf)
            elif cconf["name"] not in node.intfs:
                # Only add the p2p interface if not already there.
                other = unet.hosts[to]
                oconf = find_matching_net_config(name, cconf, other.config)
                unet.add_native_link(node, other, cconf, oconf)

    # if "dns" in config:
    write_hosts_files(unet, config.get("dns"))

    # Write our current config to the run directory
    with open(f"{unet.rundir}/config.json", "w", encoding="utf-8") as f:
        json.dump(unet.config, f, indent=2)

    return unet

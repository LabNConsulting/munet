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


def find_with_kv(l, k, v):
    if l:
        for e in l:
            if k in e and e[k] == v:
                return e
    return {}


def find_all_with_kv(l, k, v):
    rv = []
    if l:
        for e in l:
            if k in e and e[k] == v:
                rv.append(e)
    return rv


def find_matching_net_config(name, cconf, oconf):
    p = find_all_with_kv(oconf.get("connections", {}), "to", name)
    if not p:
        return {}

    rname = cconf.get("remote-name", None)
    if not rname:
        return p[0]

    return find_with_kv(p, "name", rname)


def merge_using_key(a, b, k):
    # First get a dict of indexes in `a` for the key value of `k` in objects of `a`
    m = list(a)
    mi = {o[k]: i for i, o in enumerate(m)}
    for o in b:
        bkv = o[k]
        if bkv in mi:
            m[mi[bkv]] = o
        else:
            mi[bkv] = len(m)
            m.append(o)
    return m


def list_to_dict_with_key(l, k):
    "Convert list of objects to dict using the object key `k`"
    return {x[k]: x for x in (l if l else [])}


def config_to_dict_with_key(c, ck, k):
    "Convert the config item at `ck` from a list objects to dict using the key `k`"
    c[ck] = list_to_dict_with_key(c.get(ck, []), k)
    return c[ck]


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
            search.append(str(datapath.parent))

        def logf(msg, *p, **k):
            if args.verbose:
                print("PRELOG: " + msg % p, **k, file=sys.stderr)

        config = get_config(args.log_config, "logconf", search, logf=logf)
        pathname = config["config_pathname"]
        del config["config_pathname"]

        if args.verbose:
            config["handlers"]["console"]["level"] = "DEBUG"
        logging.config.dictConfig(dict(config))
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


def validate_config(config, logger, args):
    import jsonschema  # pylint: disable=C0415

    from jsonschema.exceptions import ValidationError  # pylint: disable=C0415

    if not config:
        config = get_config(basename="munet")
        del config["config_pathname"]

    old = os.getcwd()
    if args:
        os.chdir(args.rundir)

    try:
        search = [old]
        with importlib.resources.path("munet", "munet-schema.yaml") as datapath:
            search.append(str(datapath.parent))

        schema = get_config(basename="munet-schema", search=search)
        jsonschema.validate(instance=config, schema=schema)
        logger.info("Validated")
        return True
    except FileNotFoundError as error:
        logger.info("No schema found: %s", error)
        return False
    except ValidationError as error:
        logger.info("Validation failed: %s", error)
        return False
    finally:
        if args:
            os.chdir(old)


def load_kinds(args):
    # Change CWD to the rundir prior to parsing config
    old = os.getcwd()
    if args:
        os.chdir(args.rundir)

    try:
        search = [old]
        with importlib.resources.path("munet", "kinds.yaml") as datapath:
            search.append(str(datapath.parent))

        args_config = args.kinds_config if args else None
        config = get_config(args_config, "kinds", search)
        return config_to_dict_with_key(config, "kinds", "name")
    except FileNotFoundError:
        return {}
    finally:
        if args:
            os.chdir(old)


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
    unet.config = config
    unet.config_pathname = os.path.realpath(config["config_pathname"])
    unet.config_dirname = os.path.dirname(unet.config_pathname)

    if "cli" in config:
        cli.add_cli_config(unet, config["cli"])

    kinds = load_kinds(args)
    kinds = {**kinds, **config_to_dict_with_key(config, "kinds", "name")}
    config_to_dict_with_key(kinds, "env", "name")  # convert list of env objects to dict

    config["kinds"] = kinds

    topoconf = config.get("topology")
    if not topoconf:
        return unet

    # Allow for all networks to be auto-numbered
    autonumber = topoconf.get("networks-autonumber")

    for name, conf in config_to_dict_with_key(topoconf, "networks", "name").items():
        if kind := conf.get("kind"):
            if kconf := kinds[kind]:
                conf = merge_kind_config(kconf, conf)
        conf = config_subst(conf, name=name, rundir=unet.rundir)
        if "ip" not in conf and autonumber:
            conf["ip"] = "auto"
        topoconf["networks"][name] = conf
        unet.add_network(name, conf, logger=logger)

    for name, conf in config_to_dict_with_key(topoconf, "nodes", "name").items():
        config_to_dict_with_key(
            conf, "env", "name"
        )  # convert list of env objects to dict

        if kind := conf.get("kind"):
            if kconf := kinds[kind]:
                conf = merge_kind_config(kconf, conf)

        conf = config_subst(conf, name=name, rundir=unet.rundir)
        topoconf["nodes"][name] = conf
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

    # if "dns" in topoconf:
    write_hosts_files(unet, topoconf.get("dns"))

    # Write our current config to the run directory
    with open(f"{unet.rundir}/config.json", "w", encoding="utf-8") as f:
        json.dump(unet.config, f, indent=2)

    return unet

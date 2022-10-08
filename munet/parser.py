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
"A module that implements the standalone parser."
import asyncio
import importlib.resources
import json
import logging
import logging.config
import os
import subprocess
import sys
import tempfile

from .config import config_to_dict_with_key
from .native import Munet


def get_config(pathname=None, basename="munet", search=None, logf=logging.debug):

    if not search:
        search = [os.getcwd()]
    elif isinstance(search, str):
        search = [search]

    if not pathname:
        for d in search:
            logf("%s", f'searching in "{d}" for "{basename}".{{yaml, toml, json}}')
            for ext in ("yaml", "toml", "json"):
                pathname = os.path.join(d, basename + "." + ext)
                if os.path.exists(pathname):
                    logf("%s", f'Found "{pathname}"')
                    break
            else:
                continue
            break
        else:
            raise FileNotFoundError(basename + ".{json,toml,yaml} in " + f"{search}")
    else:
        if not os.path.exists(pathname):
            if pathname[0] == "/":
                # if we have an absolute path, raise an error
                raise FileNotFoundError(pathname)

            # look in the places we know about
            for d in search:
                if os.path.exists(os.path.join(d, pathname)):
                    pathname = os.path.join(d, pathname)
                    logf("%s", f'Found "{pathname}"')
                    break
                continue
            else:
                raise FileNotFoundError(pathname + " in " + f"{search}")

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


def append_hosts_files(unet, netname):
    if not netname:
        return

    entries = []
    for name, node in unet.hosts.items():
        ifname = node.get_ifname(netname)
        if ifname in node.intf_addrs:
            entries.append((name, node.intf_addrs[ifname].ip))
    for name, node in unet.hosts.items():
        with open(os.path.join(node.rundir, "hosts.txt"), "w+", encoding="ascii") as hf:
            hf.write("\n")
            for e in entries:
                hf.write(f"{e[1]}\t{e[0]}\n")


def validate_config(config, logger, args):
    import jsonschema  # pylint: disable=C0415
    import jsonschema.validators  # pylint: disable=C0415

    from jsonschema.exceptions import ValidationError  # pylint: disable=C0415

    if not config:
        config = get_config(basename="munet")
        del config["config_pathname"]

    old = os.getcwd()
    if args:
        os.chdir(args.rundir)

    try:
        search = [old]
        with importlib.resources.path("munet", "munet-schema.json") as datapath:
            search.append(str(datapath.parent))

        schema = get_config(basename="munet-schema", search=search)
        validator = jsonschema.validators.Draft202012Validator(schema)
        validator.validate(instance=config)
        # jsonschema.validate
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

    args_config = args.kinds_config if args else None
    try:
        search = [old]
        with importlib.resources.path("munet", "kinds.yaml") as datapath:
            search.append(str(datapath.parent))

        config = get_config(args_config, "kinds", search)

        if config is not None:
            if os.path.exists(config["config_pathname"]):
                logging.info("Loaded kinds config %s", config["config_pathname"])

        return config_to_dict_with_key(config, "kinds", "name")
    except FileNotFoundError as error:
        # if we have kinds in args but the file doesn't exist, raise the error
        if args_config is not None:
            raise error
        return {}
    finally:
        if args:
            os.chdir(old)


async def async_build_topology(
    config=None, logger=None, rundir=None, args=None, pytestconfig=None
):
    if not rundir:
        rundir = tempfile.mkdtemp(prefix="unet")
    subprocess.run(f"mkdir -p {rundir} && chmod 755 {rundir}", check=True, shell=True)

    isolated = not args.host if args else True
    if not config:
        config = get_config(basename="munet")

    kinds = load_kinds(args)
    kinds = {**kinds, **config_to_dict_with_key(config, "kinds", "name")}
    config_to_dict_with_key(kinds, "env", "name")  # convert list of env objects to dict
    config["kinds"] = kinds

    unet = Munet(
        rundir=rundir,
        config=config,
        pytestconfig=pytestconfig,
        isolated=isolated,
        unshare_inline=args.unshare_inline if args else True,
        logger=logger,
    )

    try:
        await unet._async_build(logger)  # pylint: disable=W0212
    except Exception as error:
        logging.critical("Failure building munet topology: %s", error, exc_info=True)
        await unet.async_delete()
        raise

    topoconf = config.get("topology")
    if not topoconf:
        return unet

    append_hosts_files(unet, topoconf.get("dns-network"))

    # Write our current config to the run directory
    with open(f"{unet.rundir}/config.json", "w", encoding="utf-8") as f:
        json.dump(unet.config, f, indent=2)

    return unet


def build_topology(config=None, logger=None, rundir=None, args=None, pytestconfig=None):
    return asyncio.run(async_build_topology(config, logger, rundir, args, pytestconfig))

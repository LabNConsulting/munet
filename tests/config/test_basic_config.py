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
import subprocess
from subprocess import DEVNULL

from micronet import Commander
from micronet import cmd_error


commander = Commander("base")


def check(p):
    o, e = p.communicate()
    rc = p.wait()
    s = cmd_error(rc, o, e)
    if rc:
        logging.error("Failed: %s", s)
    assert not rc, s
    assert "Topology up" in e, (o, e)
    logging.info("Success: %s", s)


def test_load_default():
    p = commander.popen(["micronet"], stdin=DEVNULL)
    check(p)


def test_load_yaml_config():
    p = commander.popen(["micronet", "-c", "topology.yaml"], stdin=DEVNULL)
    check(p)


def test_load_toml_config():
    p = commander.popen(["micronet", "-c", "topology.toml"], stdin=DEVNULL)
    check(p)


def test_load_json_config():
    p = commander.popen(["micronet", "-c", "topology.json"], stdin=DEVNULL)
    check(p)

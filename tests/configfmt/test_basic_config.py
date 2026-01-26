# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# September 30 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing configuration file format variations."

import logging

import pytest

from munet import Commander
from munet import cmd_error

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


@pytest.fixture(name="stdargs")
def fixture_stdargs(rundir):
    a = [
        "uv",
        "run",
        "munet",
        "--no-kill",
        "--no-cli",
        "--no-wait",
        f"--rundir={rundir}",
    ]
    return a


def test_load_default(stdargs):
    p = commander.popen(stdargs)
    check(p)


def test_load_yaml_config(stdargs):
    p = commander.popen(stdargs + ["-c", "munet.yaml"])
    check(p)


def test_load_toml_config(stdargs):
    p = commander.popen(stdargs + ["-c", "munet.toml"])
    check(p)


def test_load_json_config(stdargs):
    p = commander.popen(stdargs + ["-c", "munet.json"])
    check(p)

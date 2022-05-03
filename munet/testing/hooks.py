# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# April 22 2022, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2022, LabN Consulting, L.L.C
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
"""A module that implements pytest hooks.

To use in your project, in your conftest.py add:

  from munet.testing.hooks import *
"""
import logging
import os
import sys

from munet.base import BaseMunet
from munet.cli import cli
from munet.testing.util import pause_test


# ===================
# Hooks (non-fixture)
# ===================


def pytest_addoption(parser):
    parser.addoption(
        "--cli-on-error",
        action="store_true",
        help="CLI on test failure",
    )
    parser.addoption(
        "--pause",
        action="store_true",
        help="Pause after each test",
    )
    parser.addoption(
        "--pause-on-error",
        action="store_true",
        help="Do not pause after (disables default when --shell or -vtysh given)",
    )
    parser.addoption(
        "--no-pause-on-error",
        dest="pause_on_error",
        action="store_false",
        help="Do not pause after (disables default when --shell or -vtysh given)",
    )


def pytest_configure(config):
    if "PYTEST_XDIST_WORKER" not in os.environ:
        os.environ["PYTEST_XDIST_MODE"] = config.getoption("dist", "no")
        os.environ["PYTEST_IS_WORKER"] = ""
        is_xdist = os.environ["PYTEST_XDIST_MODE"] != "no"
        # is_worker = False
    else:
        os.environ["PYTEST_IS_WORKER"] = os.environ["PYTEST_XDIST_WORKER"]
        is_xdist = True
        # is_worker = True

    # Turn on live logging if user specified verbose and the config has a CLI level set
    if config.getoption("--verbose") and not is_xdist and not config.getini("log_cli"):
        if config.getoption("--log-cli-level", None) is None:
            # By setting the CLI option to the ini value it enables log_cli=1
            cli_level = config.getini("log_cli_level")
            if cli_level is not None:
                config.option.log_cli_level = cli_level


def pytest_runtest_makereport(item, call):
    "Pause or invoke CLI as directed by config"

    isatty = sys.stdout.isatty()
    pause = bool(item.config.getoption("--pause"))
    if call.excinfo is None:
        error = False
    elif call.excinfo.typename == "Skipped":
        error = False
        pause = False
    else:
        error = True
        modname = item.parent.module.__name__
        exval = call.excinfo.value
        logging.error(
            "test %s/%s failed: %s: stdout: '%s' stderr: '%s'",
            modname,
            item.name,
            exval,
            exval.stdout if hasattr(exval, "stdout") else "NA",
            exval.stderr if hasattr(exval, "stderr") else "NA",
        )
        if not pause:
            pause = item.config.getoption("--pause-on-error")

    if error and isatty and item.config.getoption("--cli-on-error"):
        if not BaseMunet.g_unet:
            logging.error("Could not launch CLI b/c no munet exists yet")
        else:
            print(f"\nCLI-ON-ERROR: {call.excinfo.typename}")
            print(f"CLI-ON-ERROR:\ntest {modname}/{item.name} failed: {exval}")
            if hasattr(exval, "stdout") and exval.stdout:
                print("stdout: " + exval.stdout.replace("\n", "\nstdout: "))
            if hasattr(exval, "stderr") and exval.stderr:
                print("stderr: " + exval.stderr.replace("\n", "\nstderr: "))
            cli(BaseMunet.g_unet)

    if pause:
        if call.when == "setup":
            pause_test(f"before test '{item.nodeid}'")
        elif call.when == "teardown":
            pause_test(f"after test '{item.nodeid}'")
        elif error:
            print(f"\nPAUSE-ON-ERROR: {call.excinfo.typename}")
            print(f"PAUSE-ON-ERROR:\ntest {modname}/{item.name} failed: {exval}")
            if hasattr(exval, "stdout") and exval.stdout:
                print("stdout: " + exval.stdout.replace("\n", "\nstdout: "))
            if hasattr(exval, "stderr") and exval.stderr:
                print("stderr: " + exval.stderr.replace("\n", "\nstderr: "))
            pause_test(f"PAUSE-ON-ERROR: '{item.nodeid}'")

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
import sys

import pytest

from micronet.cleanup import cleanup_current, cleanup_previous
from micronet.cli import cli
from micronet.parser import build_topology
from micronet.base import BaseMicronet


@pytest.fixture(autouse=True, scope="session")
def session_autouse():
    if "PYTEST_TOPOTEST_WORKER" not in os.environ:
        is_worker = False
    elif not os.environ["PYTEST_TOPOTEST_WORKER"]:
        is_worker = False
    else:
        is_worker = True

    if not is_worker:
        cleanup_previous()
    yield
    if not is_worker:
        cleanup_current()


@pytest.fixture(autouse=True, scope="module")
def module_autouse(request):
    cwd = os.getcwd()
    sdir = os.path.dirname(os.path.realpath(request.fspath))
    logging.debug("changing cwd from %s to %s", cwd, sdir)
    os.chdir(sdir)
    yield
    os.chdir(cwd)


@pytest.fixture(scope="module")
def unet():
    _unet = build_topology()
    yield _unet
    _unet.delete()


# @pytest.hookimpl(hookwrapper=True)
# def pytest_runtest_call(item: pytest.Item) -> None:
#     "Hook the function that is called to execute the test."
#     yield


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
        # is_xdist = os.environ["PYTEST_XDIST_MODE"] != "no"
        # is_worker = False
    else:
        os.environ["PYTEST_IS_WORKER"] = os.environ["PYTEST_XDIST_WORKER"]
        # is_xdist = True
        # is_worker = True


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
        logging.error("test %s/%s failed: %s", modname, item.name, call.excinfo.value)
        if not pause:
            pause = item.config.getoption("--pause-on-error")

    if error and isatty and item.config.getoption("--cli-on-error"):
        if BaseMicronet.g_unet:
            cli(BaseMicronet.g_unet)
        else:
            logging.error("Could not launch CLI b/c no micronet exists yet")

    while pause and isatty:
        user = input('PAUSED, "cli" for CLI, "pdb" to debug, "Enter" to continue: ')
        user = user.strip()

        if user == "cli":
            cli(BaseMicronet.g_unet)
        elif user == "pdb":
            breakpoint()  # pylint: disable=W1515
        elif user:
            print(f'Unrecognized input: "{user}"')
        else:
            break

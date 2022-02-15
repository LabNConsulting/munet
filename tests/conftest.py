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
"Fixtures and other utilities for munet testing."
import asyncio
import logging
import os
import sys

from pathlib import Path

import pytest

from munet.base import BaseMunet
from munet.base import Bridge
from munet.cleanup import cleanup_current
from munet.cleanup import cleanup_previous
from munet.cli import cli
from munet.native import L3Node
from munet.parser import build_topology
from munet.parser import get_config


# =================
# Sessions Fixtures
# =================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    logging.debug("conftest: got event loop")
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="session")
def session_autouse():
    if "PYTEST_TOPOTEST_WORKER" not in os.environ:
        is_worker = False
    elif not os.environ["PYTEST_TOPOTEST_WORKER"]:
        is_worker = False
    else:
        is_worker = True

    if not is_worker:
        # This is unfriendly to multi-instance
        cleanup_previous()

    yield

    if not is_worker:
        cleanup_current()


# ===============
# Module Fixtures
# ===============


def get_test_logdir(nodeid=None, module=False):
    """Get log directory relative pathname."""
    xdist_worker = os.getenv("PYTEST_XDIST_WORKER", "")
    mode = os.getenv("PYTEST_XDIST_MODE", "no")

    # nodeid: all_protocol_startup/test_all_protocol_startup.py::test_router_running
    if not nodeid:
        nodeid = os.environ["PYTEST_CURRENT_TEST"].split(" ")[0]
    cur_test = nodeid.replace("[", "_").replace("]", "_")
    path, testname = cur_test.split("::")
    testname = testname.replace("/", "_")
    path = path[:-3].replace("/", ".")

    # We use different logdir paths based on how xdist is running.
    if mode == "each":
        return os.path.join(path, testname, xdist_worker)
    if mode == "load":
        return os.path.join(path, testname)
    assert mode in ("no", "loadfile", "loadscope"), f"Unknown dist mode {mode}"
    return path if module else os.path.join(path, testname)


@pytest.fixture(scope="module")
def rundir_module():
    d = os.path.join("/tmp/unet-test", get_test_logdir(module=True))
    logging.debug("conftest: test module rundir %s", d)
    return d


@pytest.fixture(autouse=True, scope="module")
def module_autouse(request):
    cwd = os.getcwd()
    sdir = os.path.dirname(os.path.realpath(request.fspath))
    logging.debug("conftest: changing cwd from %s to %s", cwd, sdir)
    os.chdir(sdir)

    yield

    os.chdir(cwd)


@pytest.fixture(scope="module")
async def unet(rundir_module):  # pylint: disable=W0621
    # Reset the class variables so auto number is predictable
    _unet = build_topology(rundir=rundir_module)
    tasks = await _unet.run()
    logging.debug("conftest: containers running")

    yield _unet

    # No one ever awaits these so cancel them
    logging.debug("conftest: canceling container waits")
    for task in tasks:
        task.cancel()
    await _unet.async_delete()

    # Reset the class variables so auto number is predictable
    logging.debug("conftest: resetting ords to 1")
    L3Node.next_ord = 1
    Bridge.next_ord = 1


# =================
# Function Fixtures
# =================


@pytest.fixture(scope="function")
def rundir():
    d = os.path.join("/tmp/unet-test", get_test_logdir(module=False))
    logging.debug("conftest: test function rundir %s", d)
    return d


# Configure logging
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item):
    d = os.path.join(
        "/tmp/unet-test", get_test_logdir(nodeid=item.nodeid, module=False)
    )
    config = item.config
    logging_plugin = config.pluginmanager.get_plugin("logging-plugin")
    filename = Path(d, "pytest-exec.log")
    logging_plugin.set_log_path(str(filename))
    logging.debug("conftest: test function setup: rundir %s", d)
    yield


@pytest.fixture
async def unet_param(request, rundir):  # pylint: disable=W0621
    """Build unet per test function with an optional topology basename parameter"""
    _unet = build_topology(config=get_config(basename=request.param), rundir=rundir)
    tasks = await _unet.run()
    logging.debug("conftest: containers running")

    yield _unet

    # No one ever awaits these so cancel them
    logging.debug("conftest: canceling container waits")
    for task in tasks:
        task.cancel()
    await _unet.async_delete()

    # Reset the class variables so auto number is predictable
    logging.debug("conftest: resetting ords to 1")
    L3Node.next_ord = 1
    Bridge.next_ord = 1


# @pytest.hookimpl(hookwrapper=True)
# def pytest_runtest_call(item: pytest.Item) -> None:
#     "Hook the function that is called to execute the test."
#     yield


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
        print(f"\nCLI-ON-ERROR: {call.excinfo.typename}")
        if BaseMunet.g_unet:
            cli(BaseMunet.g_unet)
        else:
            logging.error("Could not launch CLI b/c no munet exists yet")

    while pause and isatty:
        user = input('PAUSED, "cli" for CLI, "pdb" to debug, "Enter" to continue: ')
        user = user.strip()

        if user == "cli":
            cli(BaseMunet.g_unet)
        elif user == "pdb":
            breakpoint()  # pylint: disable=W1515
        elif user:
            print(f'Unrecognized input: "{user}"')
        else:
            break

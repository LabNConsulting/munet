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
"""A module that implements pytest fixtures.

To use in your project, in your conftest.py add:

  from munet.testing.fixtures import *
"""
import asyncio
import logging
import os

from pathlib import Path

import pytest
import pytest_asyncio

from munet.base import Bridge
from munet.cleanup import cleanup_current
from munet.cleanup import cleanup_previous
from munet.native import L3Node
from munet.parser import build_topology
from munet.parser import get_config
from munet.testing.util import async_pause_test
from munet.testing.util import pause_test


# =================
# Sessions Fixtures
# =================


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


@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    logging.debug("conftest: got event loop")
    yield loop
    loop.close()


def get_test_logdir(nodeid=None, module=False):
    """Get log directory relative pathname."""
    xdist_worker = os.getenv("PYTEST_XDIST_WORKER", "")
    mode = os.getenv("PYTEST_XDIST_MODE", "no")

    # nodeid: all_protocol_startup/test_all_protocol_startup.py::test_router_running
    if not nodeid:
        nodeid = os.environ["PYTEST_CURRENT_TEST"].split(" ")[0]
    cur_test = nodeid.replace("[", "_").replace("]", "_")
    path, testname = cur_test.split("::")
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
    # is_xdist = os.environ.get("PYTEST_XDIST_MODE", "no") != "no"
    # if "PYTEST_TOPOTEST_WORKER" not in os.environ:
    #     is_worker = False
    # elif not os.environ["PYTEST_TOPOTEST_WORKER"]:
    #     is_worker = False
    # else:
    #     is_worker = True

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
def stepf(pytestconfig):
    class Stepnum:
        "Track the stepnum in closure"
        num = 0

        def inc(self):
            self.num += 1

    pause = pytestconfig.getoption("pause")
    stepnum = Stepnum()

    def stepfunction(desc=""):
        desc = f": {desc}" if desc else ""
        if pause:
            pause_test(f"before step {stepnum.num}{desc}")
        logging.info("STEP %s%s", stepnum.num, desc)
        stepnum.inc()

    return stepfunction


@pytest_asyncio.fixture(scope="function")
async def astepf(pytestconfig):
    class Stepnum:
        "Track the stepnum in closure"
        num = 0

        def inc(self):
            self.num += 1

    pause = pytestconfig.getoption("pause")
    stepnum = Stepnum()

    async def stepfunction(desc=""):
        desc = f": {desc}" if desc else ""
        if pause:
            await async_pause_test(f"before step {stepnum.num}{desc}")
        logging.info("STEP %s%s", stepnum.num, desc)
        stepnum.inc()

    return stepfunction


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

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# August 22 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
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
"Testing of cleanup functionality."
import logging
import os

import pytest


# All tests are coroutines
# pytestmark = pytest.mark.asyncio


cleanup_paths = {}


# Check existence of cleanup files after unet is deleted
@pytest.fixture(autouse=True, scope="module")
def module_test_cleanup():
    yield
    for path in cleanup_paths.values():
        logging.info("Checking for: %s", path)
        if "noclean" not in path:
            assert os.path.exists(path)
        else:
            assert not os.path.exists(path)


# Record paths for all cleanup files
@pytest.fixture(scope="module", name="savepaths")
def savepaths_fixture(unet):
    for host in unet.hosts:
        cleanup_paths[host] = os.path.join(unet.hosts[host].rundir, "cleanup-test")
    yield


def test_containers_mounts_present(unet, savepaths):
    del savepaths
    hs1 = unet.hosts["hs1"]
    assert unet.path_exists(f"{hs1.rundir}/sock")
    assert hs1.path_exists("/tmp/sock")

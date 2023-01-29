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


# import pytest
# All tests are coroutines
# pytestmark = pytest.mark.asyncio


cleanup_paths = {}


def test_cleanup_create_unshare(unet_perfunc_unshare):
    unet = unet_perfunc_unshare

    # Record paths for all cleanup files
    for host in unet.hosts:
        cleanup_paths[host] = os.path.join(unet.hosts[host].rundir, "cleanup-test")
        assert not os.path.exists(cleanup_paths[host])


def test_munet_cleanup_unshare():
    for path in cleanup_paths.values():
        logging.debug("Checking for: %s", path)
        if "noclean" in path:
            assert not os.path.exists(path), f"Unexpected 'cleanup' file: {path}"
        else:
            assert os.path.exists(path), f"Missing 'cleanup' file: {path}"


def test_cleanup_create_nounshare(unet_perfunc_share):
    unet = unet_perfunc_share

    # Record paths for all cleanup files
    for host in unet.hosts:
        cleanup_paths[host] = os.path.join(unet.hosts[host].rundir, "cleanup-test")
        assert not os.path.exists(cleanup_paths[host])


def test_munet_cleanup_nounshare():
    for path in cleanup_paths.values():
        logging.debug("Checking for: %s", path)
        if "noclean" in path:
            assert not os.path.exists(path), f"Unexpected 'cleanup' file: {path}"
        else:
            assert os.path.exists(path), f"Missing 'cleanup' file: {path}"

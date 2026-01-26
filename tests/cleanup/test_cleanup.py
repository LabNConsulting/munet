# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# August 22 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
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

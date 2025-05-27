# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# May 20 2025, Liam Brady <lbrady@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
"Testing that configured commands properly run"
import logging

import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("host", ["h-shcmd", "h-shcmd-file", "h-pycmd", "h-pycmd-file",
                                  "h-shcmd-file-noshebang"])
async def test_config_cmd(unet_share, host):
    unet = unet_share
    rn = unet.hosts[host]
    output = rn.cmd_raises("cat cmd*.out")
    logging.debug("expects to find 'foo' in cmd.out; Found: %s", output)
    assert "foo" in output

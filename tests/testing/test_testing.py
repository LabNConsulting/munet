# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# April 22 2022, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"Test the testing fucntionality that has been imported into conftest.py"


def test_import_util():
    from munet.testing.util import pause_test # pylint: disable=C0415,W0611


def test_addopts(pytestconfig):
    assert hasattr(pytestconfig.option, "cli_on_error")
    assert hasattr(pytestconfig.option, "pause")
    assert hasattr(pytestconfig.option, "pause_on_error")

def test_stepfunction(stepf):
    stepf("the first step")
    stepf("the second step")

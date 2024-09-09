# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# April 22 2022, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"Test the testing fucntionality that has been imported into conftest.py"
import pytest

from munet.testing.util import retry


def test_import_util():
    from munet.testing.util import pause_test  # pylint: disable=C0415,W0611


def test_addopts(pytestconfig):
    assert hasattr(pytestconfig.option, "cli_on_error")
    assert hasattr(pytestconfig.option, "pause")
    assert hasattr(pytestconfig.option, "pause_on_error")


# Need to check the log for this test.
def test_stepfunction(stepf):
    stepf("the first step")
    stepf("the second step")


@retry(retry_timeout=2, retry_sleep=0.1)
def retrying_test_assert():
    if not hasattr(retrying_test_assert, "count"):
        retrying_test_assert.count = 0
    else:
        retrying_test_assert.count += 1
    assert retrying_test_assert.count == 2, "count not 2"
    retrying_test_assert.count = 0


@retry(retry_timeout=2, retry_sleep=0.1)
def retrying_test_string():
    if not hasattr(retrying_test_string, "count"):
        retrying_test_string.count = 0
    else:
        retrying_test_string.count += 1
    if retrying_test_string.count != 2:
        return "count not 2"
    return None


def test_retry_string(caplog):
    retrying_test_string()
    assert caplog.text.count("Sleeping") == 2


def test_retry_fail(caplog):
    @retry(retry_timeout=1, retry_sleep=0.1)
    def retrying_fail():
        return "Fail"

    retrying_fail(expected=False)
    assert caplog.text.count("Sleeping") == 0


def test_retry_assert_fail(caplog):
    @retry(retry_timeout=1, retry_sleep=0.2)
    def retrying_assert():
        assert False, "Fail"

    try:
        # Expected does not consider assert an expected failure
        retrying_assert(expected=False)
    except AssertionError:
        assert caplog.text.count("Sleeping") == 5
    else:
        assert False, "Failed b/c succeeded"

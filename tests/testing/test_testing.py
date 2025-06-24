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


# Assert twice then succeed
@retry(retry_timeout=2, retry_sleep=0.1)
def retrying_test_assert():
    if not hasattr(retrying_test_assert, "count"):
        retrying_test_assert.count = 0
    else:
        retrying_test_assert.count += 1
    assert retrying_test_assert.count == 2, "count not 2"


def test_retry_assert(caplog):
    retrying_test_assert()
    assert caplog.text.count("Sleeping") == 2


# Fail twice then succeed
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


# Succeed twice then fail
@retry(retry_timeout=2, retry_sleep=0.1)
def retrying_test_fail_first():
    if not hasattr(retrying_test_fail_first, "count"):
        retrying_test_fail_first.count = 0
    else:
        retrying_test_fail_first.count += 1
    if retrying_test_fail_first.count != 2:
        return None
    return "count is 2"


def test_retry_expected_fail_first(caplog):
    retrying_test_fail_first(expected=False)
    assert caplog.text.count("Sleeping") == 2


def test_retry_expected_fail(caplog):
    @retry(retry_timeout=1, retry_sleep=0.1)
    def retrying_fail():
        return "Fail"

    ret = retrying_fail(expected=False)
    assert ret == "Fail"
    assert caplog.text.count("Sleeping") == 0


def test_retry_assert_exception(caplog):
    @retry(retry_timeout=1, retry_sleep=0.2)
    def retrying_assert():
        assert False, "Fail"

    try:
        # Expected does not consider assert an expected failure by default
        retrying_assert(expected=False)
    except AssertionError:
        # Should have retried before ultimately failing
        assert caplog.text.count("Sleeping") > 0
    else:
        assert False, "Failed b/c no exception raised"


def test_retry_assert_expected(caplog):
    @retry(retry_timeout=1, retry_sleep=0.2, assert_is_except=False)
    def retrying_assert():
        assert False, "Fail"

    # Expected does not consider assert an expected failure by default
    ret = retrying_assert(expected=False)
    assert isinstance(ret, AssertionError)
    assert caplog.text.count("Sleeping") == 0


# Succeed twice then assert
@retry(retry_timeout=2, retry_sleep=0.1, assert_is_except=False)
def retrying_test_fail_first_assert():
    if not hasattr(retrying_test_fail_first_assert, "count"):
        retrying_test_fail_first_assert.count = 0
    else:
        retrying_test_fail_first_assert.count += 1
    assert retrying_test_fail_first_assert.count != 2, "count is 2"


def test_retry_assert_expected_succeed_first(caplog):
    # Expected does not consider assert an expected failure by default
    ret = retrying_test_fail_first_assert(expected=False)
    assert isinstance(ret, AssertionError)
    assert caplog.text.count("Sleeping") == 2

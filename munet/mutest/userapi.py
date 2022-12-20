# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# Copyright 2017, 2022, LabN Consulting, L.L.C.
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
"""Mutest is a simple send/expect based testing framework.

This module implements the basic send/expect functionality for mutest.  The test
developer first creates a munet topology (:ref:`munet-config`) and then writes test
scripts ("test cases") which are composed of calls to the functions defined below
("steps").  In short these are:

Send/Expect functions:

    - :py:func:`step`

    - :py:func:`step_json`

    - :py:func:`match_step`

    - :py:func:`match_step_json`

    - :py:func:`wait_step`

    - :py:func:`wait_step_json`

Control/Utility functions:

    - :py:func:`script_dir`

    - :py:func:`include`

    - :py:func:`log`

    - :py:func:`test`

Test scripts are located by the :command:`mutest` command by their name.  The name of a
test script should take the form ``mutest_TESTNAME.py`` where ``TESTNAME`` is replaced
with a user chosen name for the test case.

Here's a simple example test script which first checks that a specific forwarding entry
is in the FIB for the IP destination ``10.0.1.1``.  Then it checks repeatedly for up to
10 seconds for a second forwarding entry in the FIB for the IP destination ``10.0.2.1``.

.. code-block:: python

    match_step("r1", 'vtysh -c "show ip fib 10.0.1.1"', "Routing entry for 10.0.1.0/24",
               "Check for FIB entry for 10.0.1.1")
    wait_step("r1",
              'vtysh -c "show ip fib 10.0.2.1"',
              "Routing entry for 10.0.2.0/24",
              desc="Check for FIB entry for 10.0.2.1",
              timeout=10)

Notice that the call arguments can be specified by their correct position in the list or
using keyword names, and they can also be specified over multiple lines if preferred.

All of the functions are documented and defined below.
"""

# pylint: disable=global-statement

import functools
import json
import logging
import re
import time

from pathlib import Path
from typing import Any
from typing import Callable
from typing import Union

from deepdiff import DeepDiff as json_cmp


class TestCase:
    """A mutest testcase.

    This is normally meant to be used internally by the mutest command to
    implement the user API. See README-mutest.org for usage details on the
    user API.

    Args:
        number: identity of the test in a run.
        name: the name of the test case
        path: the test file that is being executed.
        targets: a dictionary of objects which implement ``cmd_nostatus(str)``
        output_logger: a logger for output and other messages from the test.
        result_logger: a logger to output the results of test steps to.

    Attributes:
        number: identity of the test in a run
        name: the name of the test
        targets: dictionary of targets.

        steps: total steps executed so far.
        passed: number of passing steps.
        failed: number of failing steps.

        last: the last command output.
        last_m: the last result of re.search during a matching step on the output with
            newlines converted to spaces.

    :meta private:
    """

    # sum_hfmt = "{:5.5s} {:4.4s} {:>6.6s} {}"
    # sum_dfmt = "{:5s} {:4.4s} {:^6.6s} {}"
    sum_fmt = "%6.6s %4.4s %{}s %6s  %s"

    def __init__(
        self,
        number: int,
        name: str,
        path: Path,
        targets: dict,
        output_logger: logging.Logger = None,
        result_logger: logging.Logger = None,
    ):

        self.__filename = path.absolute()
        self.__old_filenames = []
        self.__call_on_fail = None

        self.number = number
        self.name = name
        self.script_dir = self.__filename.parent
        assert self.script_dir.is_dir()
        self.targets = targets

        self.last = ""
        self.last_m = None

        self.rlog = result_logger
        self.olog = output_logger
        self.logf = functools.partial(self.olog.log, logging.INFO)
        self.steps = 0
        self.passed = 0
        self.failed = 0

        assert TestCase.g_tc is None
        TestCase.g_tc = self

        # find the longerst target name and make target field that wide
        nmax = max(len(x) for x in targets)
        nmax = max(nmax, len("TARGET"))

        self.sum_fmt = TestCase.sum_fmt.format(nmax)
        self.rlog.info(self.sum_fmt, "NUMBER", "STAT", "TARGET", "TIME", "DESCRIPTION")
        self.rlog.info("-" * 70)

        # start counting time for first step
        self.start_time = time.time()

    def __del__(self):
        if TestCase.g_tc is self:
            logging.error("Internal error, TestCase.end_test() was not called!")
            TestCase.g_tc = None

    def __push_filename(self, filename):
        fstr = "include: " + str(filename)
        self.logf(fstr)
        self.__old_filenames.append(self.__filename)
        self.__filename = filename
        self.script_dir = filename.parent

    def __pop_filename(self):
        self.__filename = self.__old_filenames.pop()
        self.script_dir = self.__filename.parent
        fstr = "return: " + str(self.__filename)
        self.logf(fstr)

    def post_result(self, target, success, rstr, logstr=None):
        if success:
            self.passed += 1
            status = "PASS"
            outlf = self.logf
            reslf = self.rlog.info
        else:
            self.failed += 1
            status = "FAIL"
            outlf = self.olog.warning
            reslf = self.rlog.warning

        self.steps += 1
        if logstr is not None:
            outlf("R:%d %s: %s" % (self.steps, status, logstr))

        run_time = time.time() - self.start_time

        stepstr = f"{self.number}.{self.steps}"
        rtimes = _delta_time_str(run_time)
        reslf(self.sum_fmt, stepstr, status, target, rtimes, rstr)
        if not success and self.__call_on_fail:
            self.__call_on_fail()

        # start counting for next step now
        self.start_time = time.time()

    def end_test(self) -> (int, int):
        """End the test log final results.

        Returns:
            number of steps, number passed, number failed, run time.
        """
        passed, failed = self.passed, self.failed

        # No close for loggers
        # self.olog.close()
        # self.rlog.close()
        self.olog = None
        self.rlog = None

        assert (
            TestCase.g_tc == self
        ), "TestCase global unexpectedly someon else in end_test"
        TestCase.g_tc = None

        return passed, failed

    def _command(
        self,
        target: str,
        cmd: str,
    ) -> str:
        """Execute a ``cmd`` and return result.

        Args:
            target: the target to execute the command on.
            cmd: string to execut on the target.
        """
        out = self.targets[target].cmd_nostatus(cmd, warn=False)
        self.last = out = out.rstrip()
        report = out if out else "<no output>"
        self.logf("COMMAND OUTPUT:\n%s", report)
        return out

    def _command_json(
        self,
        target: str,
        cmd: str,
    ) -> dict:
        """Execute a json ``cmd`` and return json result.

        Args:
            target: the target to execute the command on.
            cmd: string to execut on the target.
        """
        out = self.targets[target].cmd_nostatus(cmd, warn=False)
        self.last = out = out.rstrip()
        try:
            js = json.loads(out)
        except Exception as error:
            js = {}
            self.olog.warning(
                "JSON load failed. Check command output is in JSON format: %s",
                error,
            )
        self.logf("COMMAND OUTPUT:\n%s", out)
        return js

    def _match_command(
        self,
        target: str,
        cmd: str,
        match: str,
        flags: int,
        expect_fail: bool,
    ) -> (bool, Union[str, list]):
        """Execute a ``cmd`` and check result.

        Args:
            target: the target to execute the command on.
            cmd: string to execute on the target.
            match: regex to ``re.search()`` for in output.
            flags: python regex flags to modify matching behavior
            expect_fail: if True then succeed when the regexp doesn't match.

        Returns:
            (success, matches): if the match fails then "matches" will be None,
            otherwise if there were matching groups then groups() will be returned in
            ``matches`` otherwise group(0) (i.e., the matching text).
        """
        out = self._command(target, cmd)
        search = re.search(match, out, flags)
        self.last_m = search
        if search is None:
            success = expect_fail
            ret = None
        else:
            success = not expect_fail
            ret = search.groups()
            if not ret:
                ret = search.group(0)

            level = logging.DEBUG if success else logging.WARNING
            self.olog.log(level, "matched:%s:", ret)
        return success, ret

    def _match_command_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        expect_fail: bool,
    ) -> Union[str, dict]:
        """Execute a json ``cmd`` and check result.

        Args:
            target: the target to execute the command on.
            cmd: string to execut on the target.
            match: A json ``str`` or object (``dict``) to compare against the json
                output from ``cmd``.
            expect_fail: if True then succeed when the json doesn't match.
        """
        js = self._command_json(target, cmd)
        try:
            expect = json.loads(match)
        except Exception as error:
            expect = {}
            self.olog.warning(
                "JSON load failed. Check match value is in JSON format: %s", error
            )

        if json_diff := json_cmp(expect, js):
            success = expect_fail
            if not success:
                self.logf("JSON DIFF:%s:" % json_diff)
            return success, json_diff

        success = not expect_fail
        return success, js

    def _wait(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        expect_fail: bool,
        is_json: bool,
        timeout: float,
        interval: float,
        flags: int,
    ) -> Union[str, dict]:
        """Execute a command repeatedly waiting for result until timeout."""
        startt = time.time()
        endt = startt + timeout

        success = False
        ret = None
        while not success and time.time() < endt:
            if is_json:
                success, ret = self._match_command_json(target, cmd, match, expect_fail)
            else:
                success, ret = self._match_command(
                    target, cmd, match, flags, expect_fail
                )
            if not success:
                time.sleep(interval)
        return success, ret

    # ---------------------
    # Public APIs for User
    # ---------------------

    def include(self, pathname: str, call_on_fail: Callable[[], None] = None):
        """See :py:func:`~munet.mutest.userapi.include`.

        :meta private:
        """
        pathname = Path(pathname)
        test_file = self.script_dir.joinpath(pathname)
        self.__push_filename(pathname)
        if call_on_fail is not None:
            old_call_on_fail, self.__call_on_fail = self.__call_on_fail, call_on_fail

        try:
            script = open(test_file, "r", encoding="utf-8").read()

            # pylint: disable=possibly-unused-variable,exec-used,redefined-outer-name
            step = self.step
            step_json = self.step_json
            match_step = self.match_step
            match_step_json = self.match_step_json
            wait_step = self.wait_step
            wait_step_json = self.wait_step_json
            include = self.include
            log = self.logf

            exec(script, globals(), locals())
        except Exception as error:
            logging.error("Exception while including file: %s: %s", pathname, error)

        if call_on_fail is not None:
            self.__call_on_fail = old_call_on_fail
        self.__pop_filename()

    def step(self, target: str, cmd: str) -> str:
        """See :py:func:`~munet.mutest.userapi.step`.

        :meta private:
        """
        self.logf(
            "#%d.%d:%s:STEP:%s:%s",
            self.number,
            self.steps + 1,
            self.__filename,
            target,
            cmd,
        )
        return self._command(target, cmd)

    def step_json(self, target: str, cmd: str) -> dict:
        """See :py:func:`~munet.mutest.userapi.step_json`.

        :meta private:
        """
        self.logf(
            "#%d.%d:%s:STEP_JSON:%s:%s",
            self.number,
            self.steps + 1,
            self.__filename,
            target,
            cmd,
        )
        return self._command_json(target, cmd)

    def match_step(
        self,
        target: str,
        cmd: str,
        match: str,
        desc: str = "",
        flags: int = re.DOTALL,
        expect_fail: bool = False,
    ) -> (bool, Union[str, list]):
        """See :py:func:`~munet.mutest.userapi.match_step`.

        :meta private:
        """
        self.logf(
            "#%d.%d:%s:MATCH_STEP:%s:%s:%s:%s:%s:%s",
            self.number,
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            desc,
            flags,
            expect_fail,
        )
        success, ret = self._match_command(target, cmd, match, flags, expect_fail)
        if desc:
            self.post_result(target, success, desc)
        return success, ret

    def test(self, expr_or_value: Any, desc: str):
        """See :py:func:`~munet.mutest.userapi.test`.

        :meta private:
        """
        success = bool(expr_or_value)
        if success:
            self.post_result("", success, desc)
        return success

    def match_step_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        desc: str = "",
        expect_fail: bool = False,
    ) -> (bool, Union[str, dict]):
        """See :py:func:`~munet.mutest.userapi.match_step_json`.

        :meta private:
        """
        self.logf(
            "#%d.%d:%s:MATCH_STEP_JSON:%s:%s:%s:%s:%s",
            self.number,
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            desc,
            expect_fail,
        )
        success, ret = self._match_command_json(target, cmd, match, expect_fail)
        if desc:
            self.post_result(target, success, desc)
        return success, ret

    def wait_step(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        desc: str = "",
        timeout=10,
        interval=0.5,
        flags: int = re.DOTALL,
        expect_fail: bool = False,
    ) -> (bool, Union[str, list]):
        """See :py:func:`~munet.mutest.userapi.wait_step`.

        :meta private:
        """
        if interval is None:
            interval = min(timeout / 20, 0.25)
        self.logf(
            "#%d.%d:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s:%s",
            self.number,
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            timeout,
            interval,
            desc,
            flags,
            expect_fail,
        )
        success, ret = self._wait(
            target, cmd, match, expect_fail, False, timeout, interval, flags
        )
        if desc:
            self.post_result(target, success, desc)
        return success, ret

    def wait_step_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        desc: str = "",
        timeout=10,
        interval=None,
        expect_fail: bool = False,
    ) -> (bool, Union[str, dict]):
        """See :py:func:`~munet.mutest.userapi.wait_step_json`.

        :meta private:
        """
        if interval is None:
            interval = min(timeout / 20, 0.25)
        self.logf(
            "#%d.%d:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s",
            self.number,
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            timeout,
            interval,
            desc,
            expect_fail,
        )
        success, ret = self._wait(
            target, cmd, match, expect_fail, True, timeout, interval, 0
        )
        if desc:
            self.post_result(target, success, desc)
        return success, ret


# A non-rentrant global to allow for simplified operations
TestCase.g_tc = None

# pylint: disable=protected-access


def _delta_time_str(run_time: float) -> str:
    if run_time < 0.001:
        return f"{run_time:1.4f}"
    if run_time < 0.01:
        return f"{run_time:2.3f}"
    if run_time < 0.1:
        return f"{run_time:3.2f}"
    if run_time < 1000:
        return f"{run_time:4.1f}"
    return f"{run_time:5f}s"


def log(fmt, *args, **kwargs):
    """Log a message in the testcase output log."""
    return TestCase.g_tc.logf(fmt, *args, **kwargs)


def include(pathname: str, call_on_fail: Callable[[], None] = None):
    """Include a file as part of testcase.

    Args:
        pathname: the file to include.
        call_on_fail: function to call on step failures.
    """
    return TestCase.g_tc.include(pathname, call_on_fail)


def script_dir() -> Path:
    """The pathname to the directory containing the current script file.

    When an include() is called the script_dir is updated to be current with the
    includeded file, and is reverted to the previous value when the include completes.
    """
    return TestCase.g_tc.script_dir


def step(target: str, cmd: str) -> str:
    """Execute a ``cmd`` on a ``target`` and return the output.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execute on the target.

    Returns:
        Returns the ``str`` output of the ``cmd``.
    """
    return TestCase.g_tc.step(target, cmd)


def step_json(target: str, cmd: str) -> dict:
    """Execute a json ``cmd`` on a ``target`` and return the json object.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execute on the target.

    Returns:
        Returns the json object after parsing the ``cmd`` output.

        If json parse fails, a warning is logged and an empty ``dict`` is used.
    """
    return TestCase.g_tc.step_json(target, cmd)


def test(expr_or_value: Any, desc: str):
    """Evaluates ``expr_or_value`` and posts a result base on it bool(expr).

    If ``expr_or_value`` evaluates to a positive result (i.e., True, non-zero, non-None,
    non-empty string, non-empty list, etc..) then a PASS result is recorded, otherwise
    record a FAIL is recorded.

    Args:
        expr: an expression or value to evaluate
        desc: description of this test step.

    Returns:
        A bool indicating the test PASS or FAIL result.
    """
    return TestCase.g_tc.test(expr_or_value, desc)


def match_step(
    target: str,
    cmd: str,
    match: str,
    desc: str = "",
    flags: int = re.DOTALL,
    expect_fail: bool = False,
) -> (bool, Union[str, list]):
    """Execute a ``cmd`` on a ``target`` check result.

    Execute ``cmd`` on ``target`` and check if the regexp in ``match``
    matches or doesn't match (according to the ``expect_fail`` value) the
    ``cmd`` output.

    If the ``match`` regexp includes groups and if the match succeeds
    the group values will be returned in a list, otherwise the command
    output is returned.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execut on the ``target``.
        match: regex to match against output.
        desc: description of test, if no description then no result is logged.
        flags: python regex flags to modify matching behavior
        expect_fail: if True then succeed when the regexp doesn't match.

    Returns:
        Returns a 2-tuple. The first value is a bool indicating ``success``.
        The second value will be a list from ``re.Match.groups()`` if non-empty,
        otherwise ``re.Match.group(0)`` if there was a match otherwise None.
    """
    return TestCase.g_tc.match_step(target, cmd, match, desc, flags, expect_fail)


def match_step_json(
    target: str,
    cmd: str,
    match: Union[str, dict],
    desc: str = "",
    expect_fail: bool = False,
) -> (bool, Union[str, dict]):
    """Execute a ``cmd`` on a ``target`` check result.

    Execute ``cmd`` on ``target`` and check if the json object in ``match``
    matches or doesn't match (according to the ``expect_fail`` value) the
    json output from ``cmd``.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execut on the ``target``.
        match: A json ``str`` or object (``dict``) to compare against the json
            output from ``cmd``.
        desc: description of test, if no description then no result is logged.
        expect_fail: if True then succeed if the a json doesn't match.

    Returns:
        Returns a 2-tuple. The first value is a bool indicating ``success``. The
        second value is a ``str`` diff if there is a difference found in the json
        compare, otherwise the value is the json object (``dict``) from the ``cmd``.

        If json parse fails, a warning is logged and an empty ``dict`` is used.
    """
    return TestCase.g_tc.match_step_json(target, cmd, match, desc, expect_fail)


def wait_step(
    target: str,
    cmd: str,
    match: Union[str, dict],
    desc: str = "",
    timeout: float = 10.0,
    interval: float = 0.5,
    flags: int = re.DOTALL,
    expect_fail: bool = False,
) -> (bool, Union[str, list]):
    """Execute a ``cmd`` on a ``target`` repeatedly, looking for a result.

    Execute ``cmd`` on ``target``, every ``interval`` seconds for up to ``timeout``
    seconds until the output of ``cmd`` does or doesn't match (according to the
    ``expect_fail`` value) the ``match`` value.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execut on the ``target``.
        match: regexp to match against output.
        timeout: The number of seconds to repeat the ``cmd`` looking for a match
            (or non-match if ``expect_fail`` is True).
        interval: The number of seconds between running the ``cmd``. If not
            specified the value is calculated from the timeout value so that on
            average the cmd will execute 10 times. The minimum calculated interval
            is .25s, shorter values can be passed explicitly.
        desc: description of test, if no description then no result is logged.
        flags: python regex flags to modify matching behavior
        expect_fail: if True then succeed when the regexp *doesn't* match.

    Returns:
        Returns a 2-tuple. The first value is a bool indicating ``success``.
        The second value will be a list from ``re.Match.groups()`` if non-empty,
        otherwise ``re.Match.group(0)`` if there was a match otherwise None.
    """
    return TestCase.g_tc.wait_step(
        target, cmd, match, desc, timeout, interval, flags, expect_fail
    )


def wait_step_json(
    target: str,
    cmd: str,
    match: Union[str, dict],
    desc: str = "",
    timeout=10,
    interval=None,
    expect_fail: bool = False,
) -> (bool, Union[str, dict]):
    """Execute a cmd repeatedly and wait for matching result.

    Execute ``cmd`` on ``target``, every ``interval`` seconds until
    the output of ``cmd`` matches or doesn't match (according to the
    ``expect_fail`` value) ``match``, for up to ``timeout`` seconds.

    ``match`` is a regular expression to search for in the output of ``cmd`` when
    ``is_json`` is False.

    When ``is_json`` is True ``match`` must be a json object or a ``str`` which
    parses into a json object. Likewise, the ``cmd`` output is parsed into a json
    object and then a comparison is done between the two json objects.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execut on the ``target``.
        match: A json object or str representation of one to compare against json
            output from ``cmd``.
        desc: description of test, if no description then no result is logged.
        timeout: The number of seconds to repeat the ``cmd`` looking for a match
            (or non-match if ``expect_fail`` is True).
        interval: The number of seconds between running the ``cmd``. If not
            specified the value is calculated from the timeout value so that on
            average the cmd will execute 10 times. The minimum calculated interval
            is .25s, shorter values can be passed explicitly.
        expect_fail: if True then succeed if the a json doesn't match.

    Returns:
        Returns a 2-tuple. The first value is a bool indicating ``success``.
        The second value is a ``str`` diff if there is a difference found in the
        json compare, otherwise the value is a json object (dict) from the ``cmd``
        output.

        If json parse fails, a warning is logged and an empty ``dict`` is used.
    """
    return TestCase.g_tc.wait_step_json(
        target, cmd, match, desc, timeout, interval, expect_fail
    )


def luInclude(filename, CallOnFail=None):
    """Backward compatible API, do not use in new tests."""
    return include(filename, CallOnFail)


def luLast(usenl=False):
    """Backward compatible API, do not use in new tests."""
    return TestCase.g_tc.last_m


def luCommand(
    target,
    cmd,
    regexp=".",
    op="none",
    result="",
    ltime=10,
    returnJson=False,
    wait_time=0.5,
):
    """Backward compatible API, do not use in new tests.

    Only non-json is verified to any degree of confidence by code inspection.

    For non-json should return match.group() if match else return bool(op == "fail").

    For json if no diff return the json else diff return bool(op == "jsoncmp_fail")
     bug if no json from output (fail parse) could maybe generate diff, which could
     then return
    """
    if op == "wait":
        if returnJson:
            return wait_step_json(target, cmd, regexp, result, ltime, wait_time)

        success, _ = wait_step(target, cmd, regexp, result, ltime, wait_time)
        match = luLast()
        if success and match is not None:
            return match.group()
        return success

    if op == "none":
        if returnJson:
            return step_json(target, cmd)
        return step(target, cmd)

    if returnJson and op in ("jsoncmp_fail", "jsoncmp_pass"):
        expect_fail = op == "jsoncmp_fail"
        return match_step_json(target, cmd, regexp, result, expect_fail)

    assert not returnJson
    assert op in ("fail", "pass")
    expect_fail = op == "fail"
    success, _ = match_step(target, cmd, regexp, result, expect_fail)
    match = luLast()
    if success and match is not None:
        return match.group()
    return success

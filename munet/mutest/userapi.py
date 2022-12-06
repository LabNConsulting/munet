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
"""Implement setest functioality."""

# pylint: disable=global-statement

import functools
import json
import logging
import os
import re
import sys
import time

from pathlib import Path
from typing import Callable
from typing import Union

from deepdiff import DeepDiff as json_cmp


class TestCase:
    """A mutest testcase.

    This is normally meant to be used internally by the mutest command to
    implement the user API. See README-mutest.org for usage details on the
    user API.

    Args:
        targets: a dictionary of objects which implement ``cmd_nostatus(str)``
        script_dir: the directory from which include statements should be based.
        output_logger: a logger for output and other messages from the test.
        result_logger: a logger to output the results of test steps to.
        level: the logging level for most messages sent to the ``output_logger``.

    Attributes:
        steps: total steps executed so far.
        passed: number of passing steps.
        failed: number of failing steps.
    """

    sum_hfmt = "{:4.4s} {:>6.6s} {:4.4s} {}"
    sum_dfmt = "{:4d} {:^6.6s} {:4.4s} {}"

    def __init__(
        self,
        targets: dict,
        script_dir: Union[str, Path] = ".",
        output_logger: logging.Logger = None,
        result_logger: logging.Logger = None,
        level: int = logging.INFO,
    ):

        self.__targets = targets
        self.__script_dir = Path(script_dir)
        self.__filename = ""
        self.__old_filenames = []
        self.__call_on_fail = None
        assert self.__script_dir.is_dir()

        self.rlog = result_logger
        self.olog = output_logger
        self.logf = functools.partial(self.olog.log, level)
        self.steps = 0
        self.passed = 0
        self.failed = 0

        # self.l_last = None
        # self.l_last_nl = None
        # self.l_dotall_experiment = True

        TestCase.g_tc = self

    def __del__(self):
        if TestCase.g_tc is self:
            TestCase.g_tc = None

    def __push_filename(self, filename):
        fstr = "EXEC FILE: " + filename
        self.logf(fstr)
        self.rlog.info(fstr)
        self.__old_filenames.append(self.__filename)
        self.__filename = filename

    def __pop_filename(self):
        self.__filename = self.__old_filenames.pop()
        fstr = "RETURN TO FILE: " + self.__filename
        self.logf(fstr)
        self.rlog.info(fstr)

    def post_result(self, target, success, rstr, logstr=None):
        if success:
            self.passed += 1
            sstr = "PASS"
            outlf = self.logf
            reslf = self.rlog.info
        else:
            self.failed += 1
            sstr = "FAIL"
            outlf = self.olog.error
            reslf = self.rlog.error

        self.steps += 1
        if logstr is not None:
            outlf("R:%d %s: %s" % (self.steps, sstr, logstr))
        res = self.sum_dfmt.format(self.steps, target, sstr, rstr)
        reslf(res)
        if not success and self.__call_on_fail:
            self.__call_on_fail()

    def end_test(self):
        """End the test log final results."""
        self.rlog.info("-" * 70)
        self.rlog.info(
            "END TEST: Total steps: %d Passed: %d Failed: %d",
            self.steps,
            self.passed,
            self.failed,
        )
        # No close for loggers
        # self.olog.close()
        # self.rlog.close()
        self.olog = None
        self.rlog = None

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
        out = self.__targets[target].cmd_nostatus(cmd).rstrip()
        report = out
        if not out:
            report = "<no output>"

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
        out = self.__targets[target].cmd_nostatus(cmd).rstrip()
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
        expect_fail: bool,
    ) -> (bool, Union[str, list]):
        """Execute a ``cmd`` and check result.

        Args:
            target: the target to execute the command on.
            cmd: string to execute on the target.
            match: regex to ``re.search()`` for in output.
            expect_fail: if True then succeed when the regexp doesn't match.
        """
        out = self.__targets[target].cmd_nostatus(cmd).rstrip()
        report = out
        if not out:
            report = "<no output>"
        self.logf("COMMAND OUTPUT:\n%s", report)

        # # Experiment: can we achieve the same match behavior via DOTALL
        # # without converting newlines to spaces?
        # out_nl = out
        # search_nl = re.search(match, out_nl, re.DOTALL)
        # self.l_last_nl = search_nl
        # # Set up for comparison
        # if search_nl is not None:
        #     group_nl = search_nl.group()
        #     group_nl_converted = " ".join(group_nl.splitlines())
        # else:
        #     group_nl_converted = None

        split_out = " ".join(out.splitlines())
        search = re.search(match, split_out)
        if search is None:
            success = expect_fail
            ret = out
        else:
            success = not expect_fail
            ret = search.groups()
            if not ret:
                ret = out

            # level = logging.DEBUG if success else logging.WARNING
            # self.olog.log(level, "found:%s:" % ret)
            # # Experiment: compare matched strings obtained each way
            # if self.l_dotall_experiment and (group_nl_converted != ret):
            #     self.logf(
            #         "DOTALL experiment: strings differ dotall=[%s] orig=[%s]"
            #         % (group_nl_converted, ret),
            #         9,
            #     )
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
        expect_fail: bool = False,
        is_json: bool = False,
        timeout: float = 2.0,
        interval: float = 0.5,
        desc: str = "",
    ) -> Union[str, dict]:
        """Execute a command repeatedly waiting for result until timeout."""
        found = False
        startt = time.time()
        endt = startt + timeout

        success = False
        ret = None
        while not success and time.time() < endt:
            if is_json:
                success, ret = self._match_command_json(target, cmd, match, expect_fail)
            else:
                success, ret = self._match_command(target, cmd, match, expect_fail)
            if not success:
                time.sleep(interval)

        delta = time.time() - startt
        self.post_result(target, success, "%s +%4.2f secs" % (desc, delta))
        return found, ret

    # ---------------------
    # Public APIs for User
    # ---------------------

    def include(self, pathname: str, call_on_fail: Callable[[], None] = None):
        """See :py:func:`~munet.mutest.userapi.include`."""
        test_file = self.__script_dir.joinpath(pathname)
        self.__push_filename(pathname)
        if call_on_fail is not None:
            old_call_on_fail, self.__call_on_fail = self.__call_on_fail, call_on_fail

        self.logf("include: %s", test_file)
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
        """See :py:func:`~munet.mutest.userapi.step`."""
        self.logf(
            "#%s:%s:STEP:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
        )
        return self._command(target, cmd)

    def step_json(self, target: str, cmd: str) -> dict:
        """See :py:func:`~munet.mutest.userapi.step_json`."""
        self.logf(
            "#%s:%s:STEP_JSON:%s:%s",
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
        expect_fail: bool = False,
    ) -> (bool, Union[str, list]):
        """See :py:func:`~munet.mutest.userapi.match_step`."""
        self.logf(
            "#%s:%s:MATCH_STEP:%s:%s:%s:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            desc,
            expect_fail,
        )
        success, ret = self._match_command(target, cmd, match, expect_fail)
        self.post_result(target, success, desc)
        return success, ret

    def match_step_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        desc: str = "",
        expect_fail: bool = False,
    ) -> (bool, Union[str, dict]):
        """See :py:func:`~munet.mutest.userapi.match_step_json`."""
        self.logf(
            "#%s:%s:MATCH_STEP_JSON:%s:%s:%s:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            desc,
            expect_fail,
        )
        success, ret = self._match_command_json(target, cmd, match, expect_fail)
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
        expect_fail: bool = False,
    ) -> (bool, Union[str, list]):
        """See :py:func:`~munet.mutest.userapi.wait_step`."""
        if interval is None:
            interval = min(timeout / 20, 0.25)
        self.logf(
            "#%s:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s",
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
        return self._wait(
            target, cmd, match, expect_fail, False, timeout, interval, desc
        )

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
        """See :py:func:`~munet.mutest.userapi.wait_step_json`."""
        if interval is None:
            interval = min(timeout / 20, 0.25)
        self.logf(
            "#%s:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s",
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
        return self._wait(
            target, cmd, match, expect_fail, True, timeout, interval, desc
        )


# A non-rentrant global to allow for simplified operations
TestCase.g_tc = None

# pylint: disable=protected-access


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


def step(target: str, cmd: str) -> str:
    """Execute a ``cmd`` on a ``target`` and return the output.

    Args:
        target: the target to execute the ``cmd`` on.
        cmd: string to execute on the target.

    Returns:
        Returns ``re.Match.groups()`` if non-empty, otherwise the ``str`` output
          of the ``cmd``.
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


def match_step(
    target: str,
    cmd: str,
    match: str,
    desc: str = "",
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
        desc: description of this test step.
        expect_fail: if True then succeed when the regexp doesn't match.

    Returns:
        Returns a 2-tuple. The first value is a bool indicating ``success``.
        The second value will be a list from ``re.Match.groups()`` if non-empty,
        otherwise ``str`` output of the ``cmd``.
    """
    return TestCase.g_tc.match_step(target, cmd, match, desc, expect_fail)


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
        desc: description of this test step.
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
    timeout=10,
    interval=0.5,
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
        desc: description of this test step.
        expect_fail: if True then succeed when the regexp *doesn't* match.

    Returns:
        Returns a 2-tuple. The first value is a bool indicating ``success``.
        The second value will be a list from ``re.Match.groups()`` if non-empty,
        otherwise ``str`` output of the ``cmd``.
    """
    return TestCase.g_tc.wait_step(
        target, cmd, match, desc, timeout, interval, expect_fail
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
        desc: description of this test step.
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


# for testing
if __name__ == "__main__":
    print(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/lib")
    tc = TestCase(None)
    for arg in sys.argv[1:]:
        tc.include(arg)
    tc.end_test()
    sys.exit(0)

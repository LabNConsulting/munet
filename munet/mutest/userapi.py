#!/usr/bin/env python

# Copyright 2017, LabN Consulting, L.L.C.
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
from enum import Enum
import time

from pathlib import Path
from typing import Union

from deepdiff import DeepDiff as json_cmp


# L utility functions
#
# These functions are inteneted to provide support for CI testing within munet
# environments.

#
# This code expects the following API availability.
# a dictionary like object ``targets'' which is keyed on the target name.
#
# The target object must include a method ``cmd_nostatus'' which returns
# the output of the command's output (stdout+stderr using the same file).
#


class OP(Enum):
    NONE = -1
    FAIL = 0
    PASS = 1


class TestCase:
    """A mutest testcase.

    This is meant to be used internally by the mutest command to implement
    the user API. See README-mutest.org for details on the user API.

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
        targets,
        script_dir=".",
        output_logger=None,
        result_logger=None,
        level=logging.INFO,
    ):
        self.__targets = targets
        self.__script_dir = Path(script_dir)
        self.__filename = ""
        self.__old_filenames = []
        self.__call_on_fail = None
        assert self.__script_dir.is_dir()

        self.rlog= result_logger
        self.olog = output_logger
        self.logf = functools.partial(self.olog.log, level)
        self.steps = 0
        self.passed = 0
        self.failed = 0

        # self.l_last = None
        # self.l_last_nl = None
        # self.l_dotall_experiment = True

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
        match: str,
        op: OP = OP.NONE,
    ) -> Union[str, dict]:
        """Execute a ``cmd`` and possibly check result.

        Args:
            target: the target to execute the command on.
            cmd: string to execut on the target.
            match: regex to ``re.search()`` for in output.
            op: type of matching to be done.
        """
        if not self.__targets:
            return False
        out = self.__targets[target].cmd_nostatus(cmd).rstrip()
        report = out
        if not out:
            report = "<no output>"
        self.logf("COMMAND OUTPUT:\n", report)

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
            success = op == OP.FAIL
            ret = out
        else:
            success = op != OP.FAIL
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

    def _command_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict] = ".",
        op: OP = OP.NONE,
    ) -> Union[str, dict]:
        """Execute a json ``cmd`` and possibly check result.

        Args:
            target: the target to execute the command on.
            cmd: string to execut on the target.
            match: A json ``str`` or object (``dict``) to compare against the json
                output from ``cmd``.
            op: type of matching to be done.
        """
        if not self.__targets:
            return False

        out = self.__targets[target].cmd_nostatus(cmd).rstrip()
        try:
            js = json.loads(out)
        except Exception as error:
            js = {}
            self.olog.warning(
                "JSON load failed. Check command output is in JSON format: %s",
                error,
            )
        self.logf("COMMAND OUTPUT:\n", out)

        try:
            expect = json.loads(match)
        except Exception as error:
            expect = {}
            self.olog.warning(
                "JSON load failed. Check match value is in JSON format: %s", error
            )
        if json_diff := json_cmp(expect, js):
            success = op == "fail"
            if not success:
                self.logf("JSON DIFF:%s:" % json_diff)
            ret = json_diff
        else:
            success = op != "fail"
            ret = js
        return success, ret

    def _wait(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict] = ".",
        expect_fail: bool = False,
        is_json: bool = False,
        timeout: float = 2.0,
        interval: float = 0.5,
        desc: str = "",
    ) -> Union[str, dict]:
        """Execute a command repeatedly waiting for result until timeout"""
        found = False
        startt = time.time()
        endt = startt + timeout

        op = OP.FAIL if expect_fail else OP.PASS
        success = False
        ret = None
        while not success and time.time() < endt:
            if is_json:
                success, ret = self._command_json(target, cmd, match, op)
            else:
                success, ret = self._command(target, cmd, match, op)
            if not success:
                time.sleep(interval)

        delta = time.time() - startt
        self.post_result(target, success, "%s +%4.2f secs" % (desc, delta))
        return found, ret

    # ---------------------
    # Public APIs for User
    # ---------------------

    def include(self, filename, call_on_fail=None):
        """Include a file as part of testcase"""
        test_file = self.__script_dir.joinpath(filename)
        self.__push_filename(filename)
        if call_on_fail is not None:
            old_call_on_fail, self.__call_on_fail = self.__call_on_fail, call_on_fail

        try:
            self.logf("include: execfile " + test_file)
            with open(test_file, encoding="utf-8") as infile:
                exec(infile.read())  # pylint: disable=exec-used
        except Exception as error:
            logging.error(
                "Exception while including file: %s: %s", self.__filename, error
            )

        if call_on_fail is not None:
            self.__call_on_fail = old_call_on_fail
        self.__pop_filename()

    def step(self, target: str, cmd: str) -> Union[str, list, dict]:
        """Execute a ``cmd`` on a ``target`` and return the output.

        Args:
            target: the target to execute the ``cmd`` on.
            cmd: string to execute on the target.
        Returns:
            Returns ``re.Match.groups()`` if non-empty, otherwise the ``str`` output
              of the ``cmd``.
        """
        self.logf(
            "#%s:%s:STEP:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
        )
        return self._command(target, cmd, None, "")

    def step_json(self, target: str, cmd: str) -> Union[str, list, dict]:
        """Execute a json ``cmd`` on a ``target`` and return the json object.

        Args:
            target: the target to execute the ``cmd`` on.
            cmd: string to execute on the target.
        Returns:
            Returns the json object after parsing the ``cmd`` output.

            If json parse fails, a warning is logged and an empty ``dict`` is used.
        """
        self.logf(
            "#%s:%s:JSTEP:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
        )
        return self._command_json(target, cmd, None, "")

    def match_step(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        expect_fail: bool = False,
        desc: str = "",
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
            expect_fail: if True then succeed when the regexp doesn't match.
            desc: description of this test step.

        Returns:
            Returns a 2-tuple. The first value is a bool indicating ``success``.
            The second value will be a list from ``re.Match.groups()`` if non-empty,
            otherwise ``str`` output of the ``cmd``.
        """
        self.logf(
            "#%s:%s:MATCH_STEP:%s:%s:%s:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            expect_fail,
            desc,
        )
        op = OP.FAIL if expect_fail else OP.PASS
        success, ret = self._command(target, cmd, match, op)
        self.post_result(target, success, desc)
        return success, ret

    def match_step_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        expect_fail: bool = False,
        desc: str = "",
    ) -> (bool, Union[str, dict]):
        """Execute a ``cmd`` on a ``target`` check result.

        Execute ``cmd`` on ``target`` and check if the json object in ``match``
        matches or doesn't match (according to the ``expect_fail`` value) the
        json output from ``cmd``.

        Args:
            target: the target to execute the ``cmd`` on.
            cmd: string to execut on the ``target``.
            match (Union[str, dict()]): A json ``str`` or object (``dict``) to compare
                against the json output from ``cmd``.
            expect_fail: if True then succeed if the a json compare finds differences.
            desc: description of this test step.

        Returns:
            Returns a 2-tuple. The first value is a bool indicating ``success``. The
            second value is a ``str`` diff if there is a difference found in the json
            compare, otherwise the value is the json object (``dict``) from the ``cmd``.

            If json parse fails, a warning is logged and an empty ``dict`` is used.
        """
        self.logf(
            "#%s:%s:MATCH_STEP:%s:%s:%s:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            expect_fail,
            desc,
        )
        op = OP.FAIL if expect_fail else OP.PASS
        success, ret = self._command_json(target, cmd, match, op)
        self.post_result(target, success, desc)
        return success, ret

    def wait_step(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        expect_fail: bool = False,
        timeout=10,
        interval=0.5,
        desc: str = "",
    ) -> (bool, Union[str, list]):
        """Execute a ``cmd`` on a ``target`` repeatedly, looking for a result.

        Execute ``cmd`` on ``target``, every ``interval`` seconds for up to ``timeout``
        seconds until the output of ``cmd`` does or doesn't match (according to the
        ``expect_fail`` value) the ``match`` value.

        Args:
            target: the target to execute the ``cmd`` on.
            cmd: string to execut on the ``target``.
            match: regexp to match against output.
            expect_fail: if True then succeed when the regexp *doesn't* match.
            timeout: The number of seconds to repeat the ``cmd`` looking for a match
                (or non-match if ``expect_fail`` is True).
            interval: The number of seconds between running the ``cmd``. If not
                specified the value is calculated from the timeout value so that on
                average the cmd will execute 20 times. The minimum calculated interval
                is .1s, shorter values can be passed explicitly.
            desc: description of this test step.

        Returns:
            Returns a 2-tuple. The first value is a bool indicating ``success``.
            The second value will be a list from ``re.Match.groups()`` if non-empty,
            otherwise ``str`` output of the ``cmd``.
        """
        if interval is None:
            interval = min(timeout / 20, .1)
        self.logf(
            "#%s:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            expect_fail,
            timeout,
            interval,
            desc,
        )
        op = OP.FAIL if expect_fail else OP.PASS
        return self._wait(target, cmd, match, op, False, timeout, interval, desc)

    def wait_step_json(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict],
        expect_fail: bool = False,
        timeout=10,
        interval=None,
        desc: str = "",
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
            match (Union[str, dict()]): A json object or str representation of one to
                compare against json output from ``cmd``.
            timeout: The number of seconds to repeat the ``cmd`` looking for a match
                (or non-match if ``expect_fail`` is True).
            interval: The number of seconds between running the ``cmd``. If not
                specified the value is calculated from the timeout value so that on
                average the cmd will execute 20 times. The minimum calculated interval
                is .1s, shorter values can be passed explicitly.
            desc: description of this test step.

        Returns:
            Returns a 2-tuple. The first value is a bool indicating ``success``.
            The second value is a ``str`` diff if there is a difference found in the
            json compare, otherwise the value is a json object (dict) from the ``cmd``
            output.

            If json parse fails, a warning is logged and an empty ``dict`` is used.
        """
        if interval is None:
            interval = min(timeout / 20, .1)
        self.logf(
            "#%s:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s",
            self.steps + 1,
            self.__filename,
            target,
            cmd,
            match,
            expect_fail,
            timeout,
            interval,
            desc,
        )
        op = OP.FAIL if expect_fail else OP.PASS
        return self._wait(target, cmd, match, op, True, timeout, interval, desc)


# for testing
if __name__ == "__main__":
    print(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/lib")
    tc = TestCase(None)
    for arg in sys.argv[1:]:
        tc.include(arg)
    tc.end_test()
    sys.exit(0)

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
        targets:
        script_dir:
        output_logger
        result_logger
        level

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

        self.script_dir = Path(script_dir)
        assert self.script_dir.is_dir()

        self.reslog = result_logger
        self.outlog = output_logger
        self.logf = functools.partial(self.outlog.log, level)

        self.l_total = 0
        self.l_pass = 0
        self.l_fail = 0

        self.__filename = ""
        self.__old_filenames = []
        self.__call_on_fail = None

        self.l_last = None
        self.l_last_nl = None
        self.l_dotall_experiment = True

    def __push_filename(self, filename):
        fstr = "EXEC FILE: " + filename
        self.logf(fstr)
        self.reslog.info(fstr)
        self.__old_filenames.append(self.__filename)
        self.__filename = filename

    def __pop_filename(self):
        self.__filename = self.__old_filenames.pop()
        fstr = "RETURN TO FILE: " + self.__filename
        self.logf(fstr)
        self.reslog.info(fstr)

    def post_result(self, target, success, rstr, logstr=None):
        if success:
            self.l_pass += 1
            sstr = "PASS"
            outlf = self.logf
            reslf = self.reslog.info
        else:
            self.l_fail += 1
            sstr = "FAIL"
            outlf = self.outlog.error
            reslf = self.reslog.error

        self.l_total += 1
        if logstr is not None:
            outlf("R:%d %s: %s" % (self.l_total, sstr, logstr))
        res = self.sum_dfmt.format(self.l_total, target, sstr, rstr)
        reslf(res)
        if not success and self.__call_on_fail:
            self.__call_on_fail()

    def end_test(self):
        """End the test log final results."""
        self.reslog.info("-" * 70)
        self.reslog.info(
            "END TEST: Total Steps: %d Pass: %d Fail: %d",
            self.l_total,
            self.l_pass,
            self.l_fail,
        )
        # No close for loggers
        # self.outlog.close()
        # self.reslog.close()
        self.outlog = None
        self.reslog = None

    def _command(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict] = ".",
        op: OP = OP.NONE,
        is_json: bool = False,
    ) -> Union[str, dict]:

        """Execute a ``cmd`` and possibly check return result.

        Args:
            target: the target to execute the command on.
            cmd: string to execut on the target.
            is_json: True if result should be parsed into json object.
            match (Union[str, dict()])
        """
        if not self.__targets:
            return False
        js = None
        out = self.__targets[target].cmd_nostatus(cmd).rstrip()
        report = out
        if not out:
            report = "<no output>"
        elif is_json:
            try:
                js = json.loads(out)
            except Exception as error:
                js = {}
                self.outlog.warning(
                    "JSON load failed. Check command output is in JSON format: %s",
                    error,
                )
        self.logf("COMMAND OUTPUT:\n", report)

        # JSON comparison
        if is_json:
            try:
                expect = json.loads(match)
            except Exception as error:
                expect = {}
                self.outlog.warning(
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
            # self.outlog.log(level, "found:%s:" % ret)
            # # Experiment: compare matched strings obtained each way
            # if self.l_dotall_experiment and (group_nl_converted != ret):
            #     self.logf(
            #         "DOTALL experiment: strings differ dotall=[%s] orig=[%s]"
            #         % (group_nl_converted, ret),
            #         9,
            #     )
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
            success, ret = self._command(target, cmd, match, op, is_json)
            if not success:
                time.sleep(interval)

        delta = time.time() - startt
        self.post_result(target, success, "%s +%4.2f secs" % (desc, delta))
        return found, ret

    def include(self, filename, call_on_fail=None):
        """Include a file as part of testcase"""
        test_file = self.script_dir + "/" + filename
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

    def step(
        self, target: str, cmd: str, is_json: bool = False
    ) -> Union[str, list, dict]:

        """Execute a ``cmd`` on a ``target`` return the output.

        Args:
            target: the target to execute the ``cmd`` on.
            cmd: string to execut on the target.
            is_json: True if result should be parsed into json object.
        Returns:
            When is_json == False:
              returns ``re.Match.groups()`` if non-empty, otherwise the ``str`` output
              of the ``cmd``.
            When is_json == True:
              returns the json object (dict) after parsing the ``cmd`` output.

            If json parse fails, a warning is logged and an empty ``dict`` is used.
        """
        self.logf(
            "#%s:%s:STEP:%s:%s:%s",
            self.l_total + 1,
            self.__filename,
            target,
            cmd,
            is_json,
        )
        return self._command(target, cmd, None, "", is_json)

    def match_step(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict] = ".",
        expect_fail: bool = False,
        is_json: bool = False,
        desc: str = "",
    ) -> str:
        """Execute a ``cmd`` on a ``target`` check result.

        ``match`` is a regular expression to search for in the output of ``cmd`` when
        ``is_json`` is False.

        When ``is_json`` is True ``match`` must be a json object or a ``str`` which
        parses into a json object. Likewise, the ``cmd`` output is parsed into a json
        object and then a comparison is done between the two json objects.

        Args:
            target: the target to execute the ``cmd`` on.
            cmd: string to execut on the ``target``.
            match (Union[str, dict()]): regex str to match against output if ``is_json``
              is False, otherwise a json object or str representation of one to compare
              against parsed json output from ``cmd``.
            is_json: True if result should be parsed into json object.
            desc: description of this test step.

        Returns:
            (success, Union[str, list, dict]): Returns a 2-tuple. The first value is a
            bool indicating ``success``. The second value depends on ``is_json``:

            When is_json == False:
              value is ``re.Match.groups()`` if non-empty, otherwise ``str`` output
              of the ``cmd``.
            When is_json == True:
              The value is a ``str`` diff if there is a difference found in the json
              compare, otherwise the value is a json object (dict) from parsing the
              ``cmd`` output.

            If json parse fails, a warning is logged and an empty ``dict`` is used.
        """
        self.logf(
            "#%s:%s:MATCH_STEP:%s:%s:%s:%s:%s:%s",
            self.l_total + 1,
            self.__filename,
            target,
            cmd,
            match,
            expect_fail,
            is_json,
            desc,
        )
        op = OP.FAIL if expect_fail else OP.PASS
        success, ret = self._command(target, cmd, match, op, is_json)
        self.post_result(target, success, desc)
        return success, ret

    def wait_step(
        self,
        target: str,
        cmd: str,
        match: Union[str, dict] = ".",
        expect_fail: bool = False,
        is_json: bool = False,
        timeout=10,
        interval=0.5,
        desc: str = "",
    ):
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
            match (Union[str, dict()]): regex str to match against output if ``is_json``
              is False, otherwise a json object or str representation of one to compare
              against parsed json output from ``cmd``.
            is_json: True if result should be parsed into json object.
            timeout: The number of seconds to repeat the ``cmd`` looking for a match
              (or non-match if ``expect_fail`` is True).
            interval: The number of seconds between running the ``cmd``.
            desc: description of this test step.

        Returns:
            (success, Union[str, list, dict]): Returns a 2-tuple. The first value is a
            bool indicating ``success``. The second value depends on ``is_json``:

            When is_json == False:
              value is ``re.Match.groups()`` if non-empty, otherwise ``str`` output
              of the ``cmd``.
            When is_json == True:
              The value is a ``str`` diff if there is a difference found in the json
              compare, otherwise the value is a json object (dict) from parsing the
              ``cmd`` output.

            If json parse fails, a warning is logged and an empty ``dict`` is used.
        """
        self.logf(
            "#%s:%s:WAIT_STEP:%s:%s:%s:%s:%s:%s:%s:%s",
            self.l_total + 1,
            self.__filename,
            target,
            cmd,
            match,
            expect_fail,
            is_json,
            timeout,
            interval,
            desc,
        )
        op = OP.FAIL if expect_fail else OP.PASS
        return self._wait(target, cmd, match, op, is_json, timeout, interval, desc)

    # def do_last(self, usenl=False):
    #     if usenl:
    #         if self.l_last_nl is not None:
    #             self.outlog.debug("luLast:%s:" % self.l_last_nl.group())
    #         return self.l_last_nl
    #     if self.l_last is not None:
    #         self.outlog.debug("luLast:%s:" % self.l_last.group())
    #     return self.l_last


#
# Commands used (indirectly) by the user script. For the user script
# in the shim code, partial objects are created with names that don't include the `2'
# suffix and supply the create lutil object for that script.

# def luLast2(lutil, usenl=False):
#     return lutil.do_last(usenl)


# def luNumFail2(lutil):
#     return lutil.l_fail


# def luNumPass2(lutil):
#     return lutil.l_pass


# def luResult2(lutil, target, success, rstr, logstr=None):
#     return lutil.result(target, success, rstr, logstr)


# def luShowResults2(lutil, prFunction):
#     sf = open(lutil.fsum_name, "r", encoding="utf-8")
#     for line in sf:
#         prFunction(line.rstrip())
#     sf.close()


# def luShowFail2(lutil):
#     printed = 0
#     sf = open(lutil.fsum_name, "r", encoding="utf-8")
#     for line in sf:
#         if line[-2] != "0":
#             printed += 1
#             logging.error(line.rstrip())
#     sf.close()
#     if printed > 0:
#         logging.error("See %s for details of errors", g_lutil.fout_name)


# for testing
if __name__ == "__main__":
    print(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/lib")
    tc = TestCase(None)
    for arg in sys.argv[1:]:
        tc.include(arg)
    tc.end_test()
    sys.exit(0)

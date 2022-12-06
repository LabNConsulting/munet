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

import json
import logging
import math
import os
import re
import sys
import time

import pytest

from deepdiff import DeepDiff as json_cmp
from pytest import StashKey


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

class LUtil:
    """Base class of setest functionality."""

    l_total = 0
    l_pass = 0
    l_fail = 0
    l_filename = ""
    l_last = None
    l_line = 0
    l_dotall_experiment = False
    l_last_nl = None
    sum_hfmt = "{:4.4s} {:>6.6s} {:56.56s} {:4.4s} {:4.4s}"
    sum_dfmt = "{:4d} {:^6.6s} {:56.56s} {:4d} {:4d}"

    def __init__(
        self,
        request,
        targets,
        script_dir=".",
        log_dir=".",
        fout="output.log",
        fsum="summary.txt",
        level=6,
    ):
        assert os.path.isdir(script_dir)
        self.script_dir = script_dir
        self.log_dir = log_dir
        self.fout_name = os.path.join(log_dir, fout) if fout else None
        self.fsum_name = os.path.join(log_dir, fsum) if fsum else None
        self.l_level = level
        self.l_dotall_experiment = False
        self.l_dotall_experiment = True

        self.__targets = targets
        self.__call_on_fail = None
        self.__fout = None
        self.__fsum = None

        self.request = request
        self.item = request.node
        # store a pointer to us in the pytest request
        # print("Fixname:", request.fixturename)
        # print("Fixscope:", request.scope)
        # print("Fixnode:", request.node)
        # print("Fixfunc:", request.function)
        # print("Fixsess:", request.session)
        self.item.stash[g_stash_key] = self

    def log(self, lstr: str, level: int = 6) -> None:
        if self.l_level > 0:
            if not self.__fout:
                self.__fout = open(self.fout_name, "w", encoding="utf-8")
            self.__fout.write(lstr + "\n")
        if level <= self.l_level:
            logging.debug("%s", lstr)

    def summary(self, sstr: str) -> None:
        if not self.__fsum:
            self.__fsum = open(self.fsum_name, "w", encoding="utf-8")
            self.__fsum.write("*" * 79 + "\n")
            header = "{!s:4.4} {!s:6.6} {!s:56.56s} {:4.4s} {:4.4s}\n".format(
                "Step", "Target", "Summary", "Pass", "Fail"
            )
            self.__fsum.write(header)
            self.__fsum.write("-" * 79 + "\n")
        self.__fsum.write(sstr + "\n")

    def result(self, target, success, rstr, logstr=None):
        if success:
            p = 1
            f = 0
            self.l_pass += 1
            sstr = "PASS"
        else:
            f = 1
            p = 0
            self.l_fail += 1
            sstr = "FAIL"
        self.l_total += 1
        if logstr is not None:
            self.log("R:%d %s: %s" % (self.l_total, sstr, logstr))
        # res = "%-4d %-6s %-56s %-4d %d" % (self.l_total, target, rstr, p, f)
        res = self.sum_dfmt.format(self.l_total, target, rstr, p, f)
        self.log("R:" + res)
        self.summary(res)
        self.item.user_properties.append((self.l_total, res))
        if f == 1 and self.__call_on_fail:
            self.__call_on_fail()

    def close_files(self):
        ret = (
            "-" * 79
            + "\n"
            + f"Total: {self.l_total:<5d}"
            + " " * 57
            + f"{self.l_pass:4d} {self.l_fail:4d}"
        )
        if self.__fsum:
            self.__fsum.write(ret + "\n")
            self.__fsum.close()
            self.__fsum = None
        if self.__fout:
            if os.path.isfile(self.fsum_name):
                with open(self.fsum_name, "r", encoding="utf-8") as f:
                    self.__fout.write(f.read())
            self.__fout.close()
            self.__fout = None
        return ret

    def __set_filename(self, name):
        fstr = "FILE: " + name
        self.log(fstr)
        self.summary(fstr)
        self.l_filename = name
        self.l_line = 0

    def strToArray(self, string):
        a = []
        c = 0
        end = ""
        words = string.split()
        if len(words) < 1 or words[0].startswith("#"):
            return a
        words = string.split()
        for word in words:
            if len(end) == 0:
                a.append(word)
            else:
                a[c] += str(" " + word)
            if end == "\\":
                end = ""
            if not word.endswith("\\"):
                if end != '"':
                    if word.startswith('"'):
                        end = '"'
                    else:
                        c += 1
                else:
                    if word.endswith('"'):
                        end = ""
                        c += 1
                    else:
                        c += 1
            else:
                end = "\\"
        #        if len(end) == 0:
        #            print('%d:%s:' % (c, a[c-1]))

        return a

    def execTestFile(self, tstFile):
        if not os.path.isfile(tstFile):
            self.log("unable to read: " + tstFile)
            sys.exit(1)
            return

        f = open(tstFile, encoding="utf-8")

        for line in f:
            if len(line) <= 1:
                continue

            a = self.strToArray(line)
            if len(a) >= 6:
                luCommand2(self, a[1], a[2], a[3], a[4], a[5])
            else:
                self.l_line += 1
                self.log("%s:%s %s" % (self.l_filename, self.l_line, line))
                if len(a) >= 2:
                    if a[0] == "sleep":
                        time.sleep(int(a[1]))
                    elif a[0] == "include":
                        self.execTestFile(a[1])
        f.close()

    def command(self, target, command, regexp, op, result, returnJson, startt=None):
        if op in ("jsoncmp_pass", "jsoncmp_fail"):
            returnJson = True

        self.log(
            "%s (#%d) %s:%s COMMAND:%s:%s:%s:%s:%s:"
            % (
                time.asctime(),
                self.l_total + 1,
                self.l_filename,
                self.l_line,
                target,
                command,
                regexp,
                op,
                result,
            )
        )
        if not self.__targets:
            return False
        # self.log("Running %s %s" % (target, command))
        js = None
        out = self.__targets[target].cmd_nostatus(command).rstrip()
        if len(out) == 0:
            report = "<no output>"
        else:
            report = out
            if returnJson is True:
                try:
                    js = json.loads(out)
                except Exception:
                    js = None
                    self.log(
                        "WARNING: JSON load failed -- "
                        "confirm command output is in JSON format."
                    )
        self.log("COMMAND OUTPUT:%s:" % report)

        # JSON comparison
        if op in ("jsoncmp_pass", "jsoncmp_fail"):
            try:
                expect = json.loads(regexp)
            except Exception:
                expect = None
                self.log(
                    "WARNING: JSON load failed -- "
                    + "confirm regex input is in JSON format."
                )
            json_diff = json_cmp(expect, js)
            if len(json_diff) != 0:
                if op == "jsoncmp_fail":
                    success = True
                else:
                    success = False
                    self.log("JSON DIFF:%s:" % json_diff)
                ret = success
            else:
                if op == "jsoncmp_fail":
                    success = False
                else:
                    success = True
            self.result(target, success, result)
            if js is not None:
                return js
            # ret is unset if no json diff
            return ret

        # Experiment: can we achieve the same match behavior via DOTALL
        # without converting newlines to spaces?
        out_nl = out
        search_nl = re.search(regexp, out_nl, re.DOTALL)
        self.l_last_nl = search_nl
        # Set up for comparison
        if search_nl is not None:
            group_nl = search_nl.group()
            group_nl_converted = " ".join(group_nl.splitlines())
        else:
            group_nl_converted = None

        out = " ".join(out.splitlines())
        search = re.search(regexp, out)
        self.l_last = search
        if search is None:
            success = op == "fail"
            ret = success
        else:
            ret = search.group()
            if op != "fail":
                success = True
                level = 7
            else:
                success = False
                level = 5
            self.log("found:%s:" % ret, level)
            # Experiment: compare matched strings obtained each way
            if self.l_dotall_experiment and (group_nl_converted != ret):
                self.log(
                    "DOTALL experiment: strings differ dotall=[%s] orig=[%s]"
                    % (group_nl_converted, ret),
                    9,
                )
        if startt is not None:
            # In a wait loop
            if js is not None or ret is not False:
                delta = time.time() - startt
                self.result(target, success, "%s +%4.2f secs" % (result, delta))
        elif op in ("pass", "fail"):
            self.result(target, success, result)

        if js is not None:
            return js
        return ret

    def wait(
        self, target, command, regexp, op, result, wait, returnJson, wait_time=0.5
    ):
        self.log(
            "%s:%s WAIT:%s:%s:%s:%s:%s:%s:%s:"
            % (
                self.l_filename,
                self.l_line,
                target,
                command,
                regexp,
                op,
                result,
                wait,
                wait_time,
            )
        )
        found = False
        n = 0
        startt = time.time()

        # Calculate the amount of `sleep`s we are going to peform.
        wait_count = int(math.ceil(wait / wait_time)) + 1

        while wait_count > 0:
            n += 1
            found = self.command(
                target, command, regexp, op, result, returnJson, startt
            )
            if found is not False:
                break

            wait_count -= 1
            if wait_count > 0:
                time.sleep(wait_time)

        delta = time.time() - startt
        self.log("Done after %d loops, time=%s, Found=%s" % (n, delta, found))
        return found

    def do_include(self, filename, call_on_fail=None):
        tstFile = self.script_dir + "/" + filename
        self.__set_filename(filename)
        if call_on_fail is not None:
            old_call_on_fail = self.__call_on_fail
            self.__call_on_fail = call_on_fail
        if filename.endswith(".py"):
            self.log("luInclude: execfile " + tstFile)
            with open(tstFile, encoding="utf-8") as infile:
                exec(infile.read())  # pylint: disable=exec-used
        else:
            self.log("luInclude: execTestFile " + tstFile)
            self.execTestFile(tstFile)
        if call_on_fail is not None:
            self.__call_on_fail = old_call_on_fail

    def do_last(self, usenl=False):
        if usenl:
            if self.l_last_nl is not None:
                self.log("luLast:%s:" % self.l_last_nl.group(), 7)
            return self.l_last_nl
        if self.l_last is not None:
            self.log("luLast:%s:" % self.l_last.group(), 7)
        return self.l_last


g_stash_key = StashKey[LUtil]()

mark = pytest.mark.usefixtures("unet")


#
# Commands used by the pytest shim
#
def luStart(
    request,
    targets,
    script_dir=".",
    log_dir=".",
    fout="output.log",
    fsum="summary.txt",
    level=6,
):
    return LUtil(
        request,
        targets,
        script_dir,
        log_dir,
        fout,
        fsum,
        level,
    )


def luFinish(lutil):
    ret = lutil.close_files()
    return ret


#
# Commands used (indirectly) by the user script. For the user script
# in the shim code, partial objects are created with names that don't include the `2'
# suffix and supply the create lutil object for that script.
#


def luInclude2(lutil, filename, call_on_fail=None):
    return lutil.do_include(filename, call_on_fail)


def luCommand2(
    lutil,
    target,
    command,
    regexp=".",
    op="none",
    result="",
    ltime=10,
    returnJson=False,
    wait_time=0.5,
):
    if op != "wait":
        return lutil.command(target, command, regexp, op, result, returnJson)
    return lutil.wait(target, command, regexp, op, result, ltime, returnJson, wait_time)


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
    local_lutil = luStart(None)
    for arg in sys.argv[1:]:
        luInclude2(local_lutil, arg)
    luFinish(local_lutil)
    sys.exit(0)

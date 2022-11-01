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

import os
import re
import sys
import time
import json
import math
import logging
from deepdiff import DeepDiff as json_cmp

# L utility functions
#
# These functions are inteneted to provide support for CI testing within MiniNet
# environments.


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

    net = ""

    def __init__(
        self,
        baseScriptDir=".",
        baseLogDir=".",
        net="",
        fout="output.log",
        fsum="summary.txt",
        level=6,
    ):
        self.base_script_dir = baseScriptDir
        self.base_log_dir = baseLogDir
        self.net = net
        if fout:
            self.fout_name = baseLogDir + "/" + fout
        if fsum:
            self.fsum_name = baseLogDir + "/" + fsum
        if level is not None:
            self.l_level = level
        self.l_dotall_experiment = False
        self.l_dotall_experiment = True

        self.__call_on_fail = None
        self.__fout = None
        self.__fsum = None

    def log(self, lstr: str, level: int = 6) -> None:
        if self.l_level > 0:
            if not self.__fout:
                self.__fout = open(self.fout_name, "w", encoding="utf-8")
            self.__fout.write(lstr + "\n")
        if level <= self.l_level:
            print(lstr)

    def summary(self, sstr: str) -> None:
        if self.__fsum == "":
            self.__fsum = open(self.fsum_name, "w", encoding="utf-8")
            self.__fsum.write(
                "\
******************************************************************************\n"
            )
            self.__fsum.write(
                "\
Test Target Summary                                                  Pass Fail\n"
            )
            self.__fsum.write(
                "\
******************************************************************************\n"
            )
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
        res = "%-4d %-6s %-56s %-4d %d" % (self.l_total, target, rstr, p, f)
        self.log("R:" + res)
        self.summary(res)
        if f == 1 and self.__call_on_fail:
            self.__call_on_fail()

    def closeFiles(self):
        ret = (
            "\
******************************************************************************\n\
Total %-4d                                                           %-4d %d\n\
******************************************************************************"
            % (self.l_total, self.l_pass, self.l_fail)
        )
        if self.__fsum:
            self.__fsum.write(ret + "\n")
            self.__fsum.close()
            self.__fsum = None
        if self.__fout:
            if os.path.isfile(self.__fout):
                r = open(self.fsum_name, "r", encoding="utf-8")
                self.__fout.write(r.read())
                r.close()
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
                luCommand(a[1], a[2], a[3], a[4], a[5])
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
        if self.net == "":
            return False
        # self.log("Running %s %s" % (target, command))
        js = None
        out = self.net[target].cmd(command).rstrip()
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
        tstFile = self.base_script_dir + "/" + filename
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


# initialized by luStart
g_lutil = None

# entry calls
def luStart(
    baseScriptDir=".",
    baseLogDir=".",
    net="",
    fout="output.log",
    fsum="summary.txt",
    level=None,
):

    global g_lutil

    g_lutil = LUtil(
        baseScriptDir,
        baseLogDir,
        net,
        fout,
        fsum,
        level,
    )


def luInclude(filename, call_on_fail=None):
    return g_lutil.do_include(filename, call_on_fail)


def luCommand(
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
        return g_lutil.command(target, command, regexp, op, result, returnJson)
    return g_lutil.wait(
        target, command, regexp, op, result, ltime, returnJson, wait_time
    )


def luLast(usenl=False):
    return g_lutil.do_last(usenl)


def luFinish():
    global g_lutil
    ret = g_lutil.closeFiles()
    g_lutil = None
    return ret


def luNumFail():
    return g_lutil.l_fail


def luNumPass():
    return g_lutil.l_pass


def luResult(target, success, rstr, logstr=None):
    return g_lutil.result(target, success, rstr, logstr)


def luShowResults(prFunction):
    sf = open(g_lutil.fsum_name, "r", encoding="utf-8")
    for line in sf:
        prFunction(line.rstrip())
    sf.close()


def luShowFail():
    printed = 0
    sf = open(g_lutil.fsum_name, "r", encoding="utf-8")
    for line in sf:
        if line[-2] != "0":
            printed += 1
            logging.error(line.rstrip())
    sf.close()
    if printed > 0:
        logging.error("See %s for details of errors", g_lutil.fout_name)


# for testing
if __name__ == "__main__":
    print(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/lib")
    luStart()
    for arg in sys.argv[1:]:
        luInclude(arg)
    luFinish()
    sys.exit(0)

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# November 30 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
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
#
# pylint: disable=exec-used
"""A shim between pytest and setest"""
import functools
import glob
import os
import re

import pytest

from munet.lutil import luCommand2  # pylint: disable=W0611
from munet.lutil import luFinish  # pylint: disable=W0611
from munet.lutil import luInclude2  # pylint: disable=W0611
from munet.lutil import luStart  # pylint: disable=W0611


CWD = os.path.dirname(os.path.realpath(__file__))


# @pytest.hookimpl(tryfirst=True, hookwrapper=True)
# def pytest_runtest_makereport(item, call):
#     breakpoint()
#     outcome = yield
#     rep = outcome.get_result()
#     print(rep)


results = glob.glob(os.path.join(CWD, "setest_*.py"))
for p in results:
    base = os.path.basename(p)
    m = re.match(r"(setest_(.*)).py", str(base))
    full_name = m.group(1)
    test_name = m.group(2)
    exec(
        f"""
async def setest_{test_name}(request, unet):
    script = open("{p}", "r", encoding="utf-8").read()
    testdata = luStart(request, unet.hosts, log_dir=unet.rundir, fout="{test_name}-out.txt", fsum="{test_name}-sum.txt")
    luCommand = functools.partial(luCommand2, testdata)
    luInclude = functools.partial(luInclude2, testdata)
    try:
        exec(script, globals(), locals())
        assert testdata.l_fail == 0, f"{full_name} FAIL: steps passed: {{testdata.l_pass}} failed: {{testdata.l_fail}}"
    finally:
        result = "FAIL" if testdata.l_fail else "PASS"
        # testdata.item.add_report_section("call", "summary", f"TEST {full_name}: {{result}}: steps passed: {{testdata.l_pass}} failed: {{testdata.l_fail}}")
        luFinish(testdata)
"""
    )

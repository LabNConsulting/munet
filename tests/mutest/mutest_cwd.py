# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# February 14 2023, Christian Hopps <chopps@labn.net>
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
"""Test section and include functionality."""
from munet.mutest.userapi import include, section, test_step

# 1.1
section("A section before section include with section and include")
# 1.2
include("include/inc_secinctest.py", True)

# 1.3
test_step(True, "a test step before section include with include")
# 1.4
include("include/inc_secinctest.py", True)

# 1.5
section("A section before inline include with include")
# 1.5 and creates 2 more sections 1.6 and 1.7 and a test 1.7.1
include("include/inc_secinctest.py", False)

# 1.7.2
test_step(True, "a test step before inline include with include")
# 1.7.2
include("include/inc_secinctest.py", False)

section("A section before section include")
include("include/inc_inctest.py", False)

test_step(True, "a test step before section include")
include("include/inc_inctest.py", True)

section("A section before inline include")
include("include/inc_inctest.py", False)

test_step(True, "a test step before inline include")
include("include/inc_inctest.py", False)

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 20 2022, Christian Hopps <chopps@labn.net>
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
from munet.mutest.userapi import include
from munet.mutest.userapi import match_step
from munet.mutest.userapi import section
from munet.mutest.userapi import test


section("A section testing echo commands")
match_step("host1", "echo Hello", "Hello", "Test echo Hello")
match_step("host1", "echo World", "World", "Test echo World")

section("A section testing printf commands")
match_step("host1", 'printf "%s\n" "Hello"', "Hello", "Test printf with Hello arg")
match_step("host1", 'printf "%s\n" "World"', "World", "Test printf with World arg")

include("inc_subtest.py", new_section=True)
include("inc_withsection.py", new_section=True)

test(True, "Test after an 2 non-inline includes")
test(True, "A second test case with a target", "zoot")

section("A section with an inline include")
include("inc_subtest.py")

test(True, "A test after an inline include")

# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# February 14 2023, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
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

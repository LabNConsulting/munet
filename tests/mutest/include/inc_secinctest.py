# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
"""An include which creates a section and inline includes a test."""

from munet.mutest.userapi import include
from munet.mutest.userapi import section

section("A section before an include")
include("sectest.py")

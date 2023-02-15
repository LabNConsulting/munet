# -*- coding: utf-8 eval: (blacken-mode 1) -*-
"""An include which has a section and a test."""
from munet.mutest.userapi import section
from munet.mutest.userapi import test_step


section("A section before a test")
test_step(True, "a test")

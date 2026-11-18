# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 18 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""A module that defines munet exceptions."""


class MunetError(Exception):
    """A generic munet error."""


class MunetConfigError(MunetError):
    """Invalid munet topology or configuration."""

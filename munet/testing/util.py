# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# April 22 2022, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2022, LabN Consulting, L.L.C
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
"""Utility functions useful when using munet testing functionailty in pytest."""
import logging
import sys

from munet.base import BaseMunet
from munet.cli import cli


# =================
# Utility Functions
# =================


def pause_test(desc=""):
    isatty = sys.stdout.isatty()
    if not isatty:
        desc = f" for {desc}" if desc else ""
        logging.info("NO PAUSE on non-tty terminal%s", desc)
        return

    while True:
        if desc:
            print(f"\n== PAUSING: {desc} ==")
        user = input('PAUSED, "cli" for CLI, "pdb" to debug, "Enter" to continue: ')
        user = user.strip()
        if user == "cli":
            cli(BaseMunet.g_unet)
        elif user == "pdb":
            breakpoint()  # pylint: disable=W1515
        elif user:
            print(f'Unrecognized input: "{user}"')
        else:
            break

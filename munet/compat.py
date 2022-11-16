# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# November 16 2022, Christian Hopps <chopps@labn.net>
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
"Provide compatible APIs"


class PytestConfig:
    "Pytest config duck-type-compatible object using argprase args"

    def __init__(self, args):
        self.args = vars(args)

    def getoption(self, name, default=None, skip=False):
        assert not skip
        if name.startswith("--"):
            name = name[2:]
        name = name.replace("-", "_")
        return self.args[name] if name in self.args else default

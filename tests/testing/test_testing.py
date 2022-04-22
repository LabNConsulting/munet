# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# April 22 2022, Christian Hopps <chopps@gmail.com>
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
"Test the testing fucntionality that has been imported into conftest.py"


def test_import_util():
    from munet.testing.util import pause_test # pylint: disable=C0415,W0611


def test_addopts(pytestconfig):
    assert hasattr(pytestconfig.option, "cli_on_error")
    assert hasattr(pytestconfig.option, "pause")
    assert hasattr(pytestconfig.option, "pause_on_error")

def test_stepfunction(stepf):
    stepf("the first step")
    stepf("the second step")

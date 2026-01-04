# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# January 2 2026, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2026, LabN Consulting, L.L.C.
#

"Testing of basic topology configuration."

from munet.watchlog import WatchLog


def test_watchlog_wait(unet, stepf):
    r1 = unet.hosts["r1"]
    logpath = r1.rundir.joinpath("test_watchlog.log")
    wl = WatchLog(logpath)

    # No file yet
    stepf("Check _stat_snapshot with no file")
    assert not wl._stat_snapshot()  # pylint: disable=protected-access

    # Create the log file
    r1.cmd_raises(f"echo line-1 > {logpath}")

    snap = wl.snapshot()
    assert snap == "line-1\n"

    # Verify change
    assert not wl._stat_snapshot()  # pylint: disable=protected-access

    r1.cmd_raises(f"echo line-2 >> {logpath}")

    stepf("wait_for_match() fails for data consumed by earlier snapshot()")
    try:
        m = wl.wait_for_match(r"line-1", timeout=1)
    except TimeoutError:
        pass
    else:
        assert False, "wait_for_match() should have timed out"

    stepf("normal wait_for_match() that already exists")
    m = wl.wait_for_match(r"line-2", timeout=0)
    assert m.group(0) == "line-2"

    snap = wl.snapshot(update=False)
    assert snap == "line-2\n"

    p = r1.popen(f"for i in {{3..10}}; do sleep .5; echo line-$i; done >> {logpath}")
    assert p
    try:
        # should take about 2 seconds to get to line-4
        stepf("Check wait_for_match() that is not yet present")
        m = wl.wait_for_match(r"line-4", timeout=4)
        assert m.group(0) == "line-4"

        stepf("Check reset() and wait_for_match() earlier match")
        wl.reset()
        wl.wait_for_match(r"line-2", timeout=0.1)
        stepf("Check reset() and wait_for_match() new match")
        wl.wait_for_match(r"line-5", timeout=2)
    finally:
        p.terminate()

    stepf("Check new file and earlier wait_for_match()")
    p = r1.popen(f"for i in {{1..7}}; do sleep .1; echo line-$i; done > {logpath}")
    assert p
    try:
        wl.wait_for_match(r"line-2", timeout=2)
    finally:
        p.terminate()
        r1.cmd_status(f"rm -f {logpath}")

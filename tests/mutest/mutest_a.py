"""A file for testing send/expect steps"""
# pylint: disable=line-too-long
from munet.mutest.userapi import log, step, match_step, wait_step

output = step("r1", "ls -l /")
log("SIMPLE OUTPUT: %s", output)

# expect passing tests
match_step("r1","ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty")
match_step(target="r1",
           cmd="ls -l /dev/tty",
           match="crw.* /dev/tty",
           desc="Look for /dev/tty")
wait_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1)
wait_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, False)
wait_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, .25)
wait_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, expect_fail=False)
wait_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, .25, False)
wait_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, .25, expect_fail=False)

# expect failing tests
match_step("host1","ls -l /", " nodir", "Look for no /nodir", True)
match_step("host1","ls -l /", " nodir", "Look for no /nodir", expect_fail=True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", 1, expect_fail=True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", 1, .25, True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", 1, interval=.25, expect_fail=True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", timeout=1, expect_fail=True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", timeout=1, interval=.25, expect_fail=True)

"""A file for testing send/expect steps"""
from munet.mutest.userapi import match_step
from munet.mutest.userapi import step
from munet.mutest.userapi import wait_step


step("r1", "ls -l /")
step("host1", "ls -l /")

# expect passing tests
match_step("r1", "ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty")
match_step(
    target="r1", cmd="ls -l /dev/tty", match="crw.* /dev/tty", desc="Look for /dev/tty"
)
wait_step("r1", "sleep .2 && ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1)
wait_step(
    "r1", "sleep .2 && ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, False
)
wait_step(
    "r1", "sleep .5 && ls -l /dev/tty", "crw.* /dev/tty", "Look for /dev/tty", 1, 0.25
)
wait_step(
    "r1",
    "sleep .2 && ls -l /dev/tty",
    "crw.* /dev/tty",
    "Look for /dev/tty",
    1,
    expect_fail=False,
)
wait_step(
    "r1",
    "sleep .5 && ls -l /dev/tty",
    "crw.* /dev/tty",
    "Look for /dev/tty",
    1,
    0.25,
    False,
)
wait_step(
    "r1",
    "sleep .5 && ls -l /dev/tty",
    "crw.* /dev/tty",
    "Look for /dev/tty",
    1,
    0.25,
    expect_fail=False,
)

# expect failing tests
match_step("host1", "ls -l /", " nodir", "Look for no /nodir", True)
match_step("host1", "ls -l /", " nodir", "Look for no /nodir", expect_fail=True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", 1, expect_fail=True)
wait_step("host1", "ls -l /", " nodir", "Look for no /nodir", 1, 0.25, True)
wait_step(
    "host1",
    "ls -l /",
    " nodir",
    "Look for no /nodir",
    1,
    interval=0.25,
    expect_fail=True,
)
wait_step(
    "host1", "ls -l /", " nodir", "Look for no /nodir", timeout=1, expect_fail=True
)
wait_step(
    "host1",
    "ls -l /",
    " nodir",
    "Look for no /nodir",
    timeout=1,
    interval=0.25,
    expect_fail=True,
)

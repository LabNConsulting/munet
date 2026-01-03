"""Test basic container functionality."""

from munet.mutest.userapi import match_step, section, step, get_target, test_step

# from munet.base import BaseMunet
# from munet.cli import async_cli
# await async_cli(BaseMunet.g_unet)

test_step(get_target("r2").cmd_p is not None, "Verify container is up and running")

section("Test network connectivity")

match_step(
    "r1",
    "ping -w1 -c1 10.0.1.2",
    "0% packet loss",
    "Ping container r2 from host r1 over net0",
)

match_step(
    "r1",
    "ping -w1 -c1 10.254.1.1",
    "0% packet loss",
    "Ping container r2 from host r1 over p2p connection",
)

match_step(
    "r2",
    "ping -w1 -c1 10.0.1.1",
    "0% packet loss",
    "Ping host r1 from container r2 over net0",
)

match_step(
    "r2",
    "ping -w1 -c1 10.254.1.0",
    "0% packet loss",
    "Ping host r1 from container r2 over p2p connection",
)

match_step(
    "r2",
    "df -T | egrep '/mytmp'",
    "tmpfs +tmpfs +52[0-9][0-9][0-9][0-9] .*/mytmp",
    "verify tmpfs size",
)

section("Test container mounts")

step("r2", "echo foobar > /mytmp/foobar.txt")
match_step("r2", "cat /mytmp/foobar.txt", "foobar", "verify tmpfs mount works")

step("r2", "echo foobar > /mybind/foobar.txt")
match_step(
    ".",
    "cat /tmp/mutest/mutest_basic_container/r2/mybind/foobar.txt",
    "foobar",
    "verify bind mount works",
)

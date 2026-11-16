"""Test background command steps and send/expect functionality."""

import re
import shlex
import uuid

from munet.mutest.userapi import background_match_step
from munet.mutest.userapi import background_match_step_json
from munet.mutest.userapi import background_start
from munet.mutest.userapi import background_step
from munet.mutest.userapi import background_step_json
from munet.mutest.userapi import section
from munet.mutest.userapi import step
from munet.mutest.userapi import test_step
from munet.mutest.userapi import wait_step


section("Test background_step and stdout/stderr capture")
pid = background_start(
    "r1",
    "echo 'stdout message'; echo 'stderr message' >&2; touch /tmp/mutest-bg-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
step("r1", "rm -f /tmp/mutest-bg-done")
out = background_step(pid)
test_step(
    "stdout message" in out and "stderr message" in out,
    "Verify background stdout/stderr capture",
    "r1",
)

section("Test background_step API misuse")
# An ending step consumes the PID. A second ending step is invalid usage.
try:
    background_step(pid)
except KeyError:
    test_step(True, "Reject a previously consumed background PID", "r1")
else:
    test_step(False, "Reject a previously consumed background PID", "r1")

try:
    background_step(-12345)
except KeyError:
    test_step(True, "Reject an unknown background PID", "r1")
else:
    test_step(False, "Reject an unknown background PID", "r1")

section("Test positive background_match_step calls")
step("r1", "rm -f /tmp/mutest-bg-match-done")
pid = background_start(
    "r1",
    "echo 'Neighbor 10.0.0.1 established'; touch /tmp/mutest-bg-match-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-match-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
step("r1", "rm -f /tmp/mutest-bg-match-done")
result = background_match_step(
    pid,
    r"Neighbor (\S+) established",
    "Match background command output",
)
test_step(
    result is not None,
    "Verify background_match_step returns a match",
    "r1",
)

pid = background_start(
    "r1",
    "printf 'first line\\nsecond line\\n'; touch /tmp/mutest-bg-match-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-match-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
step("r1", "rm -f /tmp/mutest-bg-match-done")
success, matched = background_match_step(
    pid,
    "first line\nsecond line",
    "Match exact multiline background output",
    exact_match=True,
)
test_step(
    success and matched == "first line\nsecond line",
    "Return the exact matching text",
    "r1",
)


section("Test negative (expect_fail) background_match_step calls")
pid = background_start(
    "r1",
    "printf 'interface UP\\n'; touch /tmp/mutest-bg-match-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-match-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
step("r1", "rm -f /tmp/mutest-bg-match-done")
success, matched = background_match_step(
    pid,
    "interface DOWN",
    "Verify that background output does not contain DOWN",
    expect_fail=True,
)
test_step(
    success and matched is None,
    "Return success for the expected absence of a regex match",
    "host1",
)


section("Test background commands across sections")
step("r1", "rm -f /tmp/mutest-bg-section-done")
pid = background_start(
    "r1",
    "echo 'background across sections'; "
    "touch /tmp/mutest-bg-section-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-section-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)

section("Complete background commands started in a previous section")
out = background_step(pid)
test_step(
    "background across sections" in out,
    "Verify background command survives section changes",
    "r1",
)
step("r1", "rm -f /tmp/mutest-bg-section-done")


section("Test background commands across includes")
step("r1", "rm -f /tmp/mutest-bg-section-done")
pid = background_start(
    "r1",
    "echo 'background across includes'; "
    "touch /tmp/mutest-bg-include-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-include-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
include("include/inc_subtest.py")
out = background_step(pid)
test_step(
    "background across includes" in out,
    "Verify background command survives include changes",
    "r1",
)
step("r1", "rm -f /tmp/mutest-bg-include-done")


section("Test background_step_json")
step("r1", "rm -f /tmp/mutest-bg-json-done")
pid = background_start(
    "r1",
    """echo '{"status": "ok", "count": 3}'; touch /tmp/mutest-bg-json-done""",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-json-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
result = background_step_json(pid)
test_step(
    result == {"status": "ok", "count": 3},
    "Verify background_step_json parses valid JSON",
    "r1",
)
step("r1", "rm -f /tmp/mutest-bg-json-done")


step("r1", "rm -f /tmp/mutest-bg-json-done")
pid = background_start(
    "r1",
    """echo 'not json'; touch /tmp/mutest-bg-json-done""",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-json-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
result = background_step_json(pid)
test_step(
    result == {},
    "Verify background_step_json handles invalid JSON",
    "r1",
)
step("r1", "rm -f /tmp/mutest-bg-json-done")


section("Test positive background_match_step_json calls")
step("r1", "rm -f /tmp/mutest-bg-json-match-done")
pid = background_start(
    "r1",
    """echo '{"status": "ok", "count": 3, "neighbor": "10.0.0.1"}'; """
    "touch /tmp/mutest-bg-json-match-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-json-match-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
result = background_match_step_json(
    pid,
    {"status": "ok", "count": 3},
    "Verify background JSON subset matching",
)
test_step(
    result is not None,
    "Verify background_match_step_json returned a match",
    "r1",
)

step("r1", "rm -f /tmp/mutest-bg-json-match-done")
pid = background_start(
    "r1",
    """echo '{"status": "ok", "count": 3}'; """
    "touch /tmp/mutest-bg-json-exact-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-json-exact-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
result = background_match_step_json(
    pid,
    {"status": "ok", "count": 3},
    "Verify exact background JSON matching",
    exact_match=True,
)
test_step(
    result is not None,
    "Verify exact background JSON match succeeds",
    "r1",
)


section("Test negative (expect_fail) background_match_step_json calls")
step("r1", "rm -f /tmp/mutest-bg-json-exact-done")
pid = background_start(
    "r1",
    """echo '{"status": "failed", "count": 3}'; """
    "touch /tmp/mutest-bg-json-fail-done",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-json-fail-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
result = background_match_step_json(
    pid,
    {"status": "ok"},
    "Verify expected background JSON mismatch",
    expect_fail=True,
)
test_step(
    result is not None,
    "Verify expected JSON mismatch is recognized",
    "r1",
)
step("r1", "rm -f /tmp/mutest-bg-json-fail-done")


section("Test background matching with nonzero exit status")
step("r1", "rm -f /tmp/mutest-bg-nonzero")
pid = background_start(
    "r1",
    "echo 'expected output'; touch /tmp/mutest-bg-nonzero; exit 42",
)
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-nonzero && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
background_match_step(
    pid,
    "expected output",
    "Match output from a command with nonzero exit status",
)
step("r1", "rm -f /tmp/mutest-bg-nonzero")


section("Test simultaneous background commands")
step("r1", "rm -f /tmp/mutest-bg-r1-done")
step("host1", "rm -f /tmp/mutest-bg-host1-done")
pid1 = background_start(
    "r1",
    "echo 'output from r1'; touch /tmp/mutest-bg-r1-done",
)
pid2 = background_start(
    "host1",
    "echo 'output from host1'; touch /tmp/mutest-bg-host1-done",
)
# Wait for both commands to produce their output.
wait_step(
    "r1",
    "test -f /tmp/mutest-bg-r1-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
wait_step(
    "host1",
    "test -f /tmp/mutest-bg-host1-done && echo READY",
    "READY",
    timeout=5,
    interval=0.1,
)
# Complete the commands in reverse order.
out2 = background_step(pid2)
out1 = background_step(pid1)
test_step(
    "output from host1" in out2 and "output from r1" not in out2,
    "Verify host1 background output",
    "host1",
)
test_step(
    "output from r1" in out1 and "output from host1" not in out1,
    "Verify r1 background output",
    "r1",
)
step("r1", "rm -f /tmp/mutest-bg-r1-done")
step("host1", "rm -f /tmp/mutest-bg-host1-done")

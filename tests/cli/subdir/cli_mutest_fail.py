"""Intentionally failing CLI test fixture."""
from munet.mutest.userapi import match_step
match_step("r1", "echo CLI_FAIL_INPUT", "DOES_NOT_MATCH", "CLI deliberate failure")

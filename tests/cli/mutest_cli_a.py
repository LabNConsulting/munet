"""CLI test fixture A."""
from munet.mutest.userapi import match_step
match_step("r1", "echo CLI_A_OK", "CLI_A_OK", "CLI marker A")

"""CLI test fixture B."""
from munet.mutest.userapi import match_step
match_step("r1", "echo CLI_B_OK", "CLI_B_OK", "CLI marker B")

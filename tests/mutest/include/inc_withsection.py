"""An include file for testing section and nested include"""

from munet.mutest.userapi import include, match_step, section, wait_step

match_step("r1", "hostname", "r1", "Verify correct hostname")

section("The waiting section of this include")
wait_step("r1", "sleep .1; hostname", "r1", "Verify correct hostname with sleep;")
wait_step("r1", "sleep .1; ls -l /", "etc", "Verify etc in rootfs /")

include("inc_subtest.py", new_section=True)

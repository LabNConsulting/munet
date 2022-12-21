"""An include file for testing hostname command"""
from munet.mutest.userapi import match_step
from munet.mutest.userapi import wait_step


match_step("r1", "hostname", "r1", "Verify correct hostname")
wait_step("r1", "sleep .1; hostname", "r1", "Verify correct hostname with sleep;")
wait_step("r1", "sleep .1 && hostname", "r1", "Verify correct hostname with sleep &&")

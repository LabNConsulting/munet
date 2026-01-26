"""An include file for testing hostname command

This is a first level include within a sub-direction of the main test.
"""

from munet.mutest.userapi import include
from munet.mutest.userapi import match_step
from munet.mutest.userapi import step
from munet.mutest.userapi import test_step
from munet.mutest.userapi import wait_step

# include as new section
include("checknorm.py", True)

# section("A sub-section")
match_step("r1", "hostname", "r1", "Verify correct hostname")
wait_step("r1", "sleep .1; hostname", "r1", "Verify correct hostname with sleep;")
wait_step("r1", "sleep .1 && hostname", "r1", "Verify correct hostname with sleep &&")

# section("A second sub-section")
test_step(True, "a sub-section(2nd) test step")
step("r1", "echo sub-section(2nd) step")
test_step(True, "another sub-section(2nd) test step")

# include inline
# include('checknorm.py')

test_step(True, "final sub-section(2nd) test step")

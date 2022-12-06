# pylint: disable=line-too-long
"""A test of json steps"""
from munet.mutest.userapi import include, log, step_json, match_step_json, wait_step_json

js = step_json("r1", 'echo { "name": "chopps" }')
log("SIMPLE JSON: %s", js)

# expect passing tests
match_step_json("r1",'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps")
wait_step_json("r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps", 1, .25)
wait_step_json("r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps", 1, .25, False)
wait_step_json("r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps", 1, interval=.25)
wait_step_json("r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps", 1, interval=.25, expect_fail=False)
wait_step_json("r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps", timeout=1, interval=.25)
wait_step_json("r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps", timeout=1, interval=.25, expect_fail=False)

# expect failing tests
include("inc_b_fail.py")

"""A include file for testing json steps"""
# pylint: disable=line-too-long
from munet.mutest.userapi import match_step_json, wait_step_json

match_step_json("r1","""echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", True)
match_step_json("r1","""echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", expect_fail=True)
wait_step_json("r1", """echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", 1, expect_fail=True)
wait_step_json("r1", """echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", 1, .25, True)
wait_step_json("r1", """echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", 1, interval=.25, expect_fail=True)
wait_step_json("r1", """echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", timeout=1, expect_fail=True)
wait_step_json("r1", """echo '{ "name": "other" }'""", '{ "name": "chopps"}', "Look for no chopps", timeout=1, interval=.25, expect_fail=True)
wait_step_json("r1", """echo 'not json'""", '{ "name": "other" }', "Look for chopps", 1, .25, True)
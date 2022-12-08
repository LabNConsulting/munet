"""A test of json steps"""
from munet.mutest.userapi import include
from munet.mutest.userapi import log
from munet.mutest.userapi import match_step_json
from munet.mutest.userapi import step_json
from munet.mutest.userapi import wait_step_json


js = step_json("r1", 'echo { "name": "chopps" }')
log("SIMPLE JSON: %s", js)

# expect passing tests
match_step_json(
    "r1", 'echo \'{ "name": "chopps" }\'', '{ "name": "chopps"}', "Look for chopps"
)
wait_step_json(
    "r1",
    'echo \'{ "name": "chopps" }\'',
    '{ "name": "chopps"}',
    "Look for chopps",
    1,
    0.25,
)
wait_step_json(
    "r1",
    'echo \'{ "name": "chopps" }\'',
    '{ "name": "chopps"}',
    "Look for chopps",
    1,
    0.25,
    False,
)
wait_step_json(
    "r1",
    'echo \'{ "name": "chopps" }\'',
    '{ "name": "chopps"}',
    "Look for chopps",
    1,
    interval=0.25,
)
wait_step_json(
    "r1",
    'echo \'{ "name": "chopps" }\'',
    '{ "name": "chopps"}',
    "Look for chopps",
    1,
    interval=0.25,
    expect_fail=False,
)
wait_step_json(
    "r1",
    'echo \'{ "name": "chopps" }\'',
    '{ "name": "chopps"}',
    "Look for chopps",
    timeout=1,
    interval=0.25,
)
wait_step_json(
    "r1",
    'echo \'{ "name": "chopps" }\'',
    '{ "name": "chopps"}',
    "Look for chopps",
    timeout=1,
    interval=0.25,
    expect_fail=False,
)

# expect failing tests
include("inc_b_fail.py")

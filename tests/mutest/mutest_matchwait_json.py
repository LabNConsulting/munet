"""Test match and wait send/expect-json step functionality."""
from munet.mutest.userapi import log
from munet.mutest.userapi import match_step_json
from munet.mutest.userapi import section
from munet.mutest.userapi import step_json
from munet.mutest.userapi import wait_step_json


js = step_json("r1", 'echo { "name": "chopps" }')
log("SIMPLE JSON: %s", js)

# expect passing tests

section("Test positive match_step_json calls")

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

section("Test negative (expect_fail) match_step_json calls")

match_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    True,
)
match_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    expect_fail=True,
)
wait_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    1,
    expect_fail=True,
)
wait_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    1,
    0.25,
    True,
)
wait_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    1,
    interval=0.25,
    expect_fail=True,
)
wait_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    timeout=1,
    expect_fail=True,
)
wait_step_json(
    "r1",
    """echo '{ "name": "other" }'""",
    '{ "name": "chopps"}',
    "Look for no chopps",
    timeout=1,
    interval=0.25,
    expect_fail=True,
)
wait_step_json(
    "r1", """echo 'not json'""", '{ "name": "other" }', "Look for chopps", 1, 0.25, True
)

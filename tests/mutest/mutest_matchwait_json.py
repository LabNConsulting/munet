"""Test match and wait send/expect-json step functionality."""
from munet.mutest.userapi import log
from munet.mutest.userapi import match_step
from munet.mutest.userapi import match_step_json
from munet.mutest.userapi import section
from munet.mutest.userapi import script_dir
from munet.mutest.userapi import step_json
from munet.mutest.userapi import test_step
from munet.mutest.userapi import wait_step_json


js = step_json("r1", """printf '{ "name": "chopps" }'""")
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

section("Test json exact matching (exact_match == True)")

match_step_json(
    "r1",
    """echo '[{ "name": "other" }]'""",
    '[{ "name": "chopps"}]',
    "Look for no chopps",
    expect_fail=True,
    exact_match=True,
)
wait_step_json(
    "r1",
    """echo '[{ "name": "other" }]'""",
    '[{ "name": "chopps"}]',
    "Look for no chopps",
    1,
    expect_fail=True,
    exact_match=True,
)
match_step_json(
    "r1",
    """echo '[{ "name": "chopps" }]'""",
    '[{ "name": "chopps"}]',
    "Look for chopps",
    exact_match=True,
)
wait_step_json(
    "r1",
    """echo '[{ "name": "chopps" }]'""",
    '[{ "name": "chopps"}]',
    "Look for chopps",
    1,
    exact_match=True,
)

section("Test json matching rules (exact_match == False)")

json1 = '{"foo":"foo"}'
json2 = '{"foo":"foo", "bar":"bar"}'

_, ret = match_step_json(
    "r1",
    f"echo '{json2}'",
    json1,
    "Data within output object present",
)
test_step(
    ret == {'foo': 'foo', 'bar': 'bar'},
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json1}'",
    json2,
    "Data within output object not present",
    expect_fail=True,
)
test_step(
    ret == {'dictionary_item_removed': ["root['bar']"]},
    "    Correct return value",
)
# The return type should be a mix of dicts and lists. Not custom DeepDiff types!
test_step(
    type(ret['dictionary_item_removed']) is list,
    "    Correct return value type",
)

json1 = '[{"foo":"foo"}]'
json2 = '[{"foo":"foo"}, {"bar":"bar"}]'
json3 = [{"bar": "bar"}, {"foo": "foo"}]

_, ret = match_step_json(
    "r1",
    f"echo '{json2}'",
    json1,
    "Objects within output array present",
)
test_step(
    ret == [{'foo': 'foo'}, {'bar': 'bar'}],
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json1}'",
    json2,
    "Objects within output array not present",
    expect_fail=True,
)
test_step(
    ret == {'iterable_item_removed': {'root[1]': {'bar': 'bar'}}},
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json2}'",
    json3,
    "Both objects within output array present",
)
test_step(
    ret == [{'foo': 'foo'}, {'bar': 'bar'}],
    "    Correct return value",
)

json1 = '["foo"]'
json2 = '["foo", "bar"]'
json3 = '["bar", "foo"]'

_, ret = match_step_json(
    "r1",
    f"echo '{json2}'",
    json1,
    "Data in one array is a subset of another"
)
test_step(
    ret == ['foo', 'bar'],
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json1}'",
    json2,
    "Data in different arrays don't match",
    expect_fail=True,
)
test_step(
    ret == {'iterable_item_removed': {'root[1]': 'bar'}},
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json2}'",
    json3,
    "Data in equivalent arrays match"
)
test_step(
    ret == ['foo', 'bar'],
    "    Correct return value",
)

json1 = '{"level1": ["level2", {"level3": ["level4"]}]}'
json2 = '{"level1": ["level2", {"level3": ["level4"], "l3": "l4"}]}'
json3 = '{"level1": ["level2", {"level3": ["level4", {"level5": "l6"}]}]}'
json4 = '{"level1": ["level2", {"level3": ["level4", "l4"]}]}'

_, ret = match_step_json(
    "r1",
    f"echo '{json2}'",
    json1,
    "Data within output object present (nested)",
)
test_step(
    ret == {'level1': ['level2', {'level3': ['level4'], 'l3': 'l4'}]},
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json3}'",
    json1,
    "Objects within output array present (nested)",
)
test_step(
    ret == {'level1': ['level2', {'level3': ['level4', {'level5': 'l6'}]}]},
    "    Correct return value",
)
_, ret = match_step_json(
    "r1",
    f"echo '{json4}'",
    json1,
    "Data in one array is a subset of another"
)
test_step(
    ret == {"level1": ["level2", {"level3": ["level4", "l4"]}]},
    "    Correct return value",
)
match_step_json(
    "r1",
    """echo '{}'""",
    '{ "name": "chopps"}',
    "empty json output doesn't match",
    expect_fail=True,
    exact_match=False,
)

# This case only passes when json_cmp (DeepDiff) is given
# the arg `cutoff_intersection_for_pairs` at 0.8 or higher
# the default value is 0.7. Interestingly, if we do not provide
# `ignore_order=True` it also passes.
full = '[{"1one": 1, "1two": 2}, {"2one": 1, "2two": 2}]'
subset = '[{"1one": 1}, {"2one": 1}]'

match_step_json(
    "r1",
    f"echo '{full}'",
    subset,
    "Verify subset matches full",
    expect_fail=False,
    exact_match=False,
)

# This case only passes when json_cmp (DeepDiff) is given
# the arg `cutoff_distance_for_pairs` at 0.4 or higher
# the default value is 0.3.
full = '[{"1one": 1, "1two": 2, "1three": 3, "1four": 4, "1five": 5, "1six": 6}, {"2one": 1, "2two": 2, "2three": 3, "2four": 4, "2five": 5, "2six": 6}]'
subset = '[{"2three": 3}]'

match_step_json(
    "r1",
    f"echo '{full}'",
    subset,
    "Verify alternate subset matches full",
    expect_fail=False,
    exact_match=False,
)

section("Test json errors")

jsonblank = '{}'
jsongood = '{"foo":"bar"}'
jsonbad = '{"bad":"trailing-comma",}'

_, ret = match_step_json(
    "r1",
    f"echo '{jsongood}'",
    jsongood,
    "Output json is good, match json is good, expect pass",
)

_, ret = match_step_json(
    "r1",
    f"echo '{jsongood}'",
    jsonblank,
    "Output json is good, match json is blank, expect pass",
)


_, ret = match_step(
    ".",
    f"cd {script_dir()} && mutest -d $MUNET_RUNDIR/failtest2 --file-select='mufail_*'",
    "run stats: 4 steps, 0 pass, 4 fail",
    "Expect 4 failures for 4 bad json variations",
)

# _, ret = match_step_json(
#     "r1",
#     f"echo '{jsonbad}'",
#     jsongood,
#     "Output json is bad, match json is good, fail is pass",
#     expect_fail=True,
# )

# _, ret = match_step_json(
#     "r1",
#     f"echo '{jsonbad}'",
#     jsonblank,
#     "Output json is bad, match json is blank, fail is pass",
#     expect_fail=True,
# )

# _, ret = match_step_json(
#     "r1",
#     f"echo '{jsongood}'",
#     jsonbad,
#     "Output json is good, match json is bad, fail is pass",
#     expect_fail=True,
# )

# _, ret = match_step_json(
#     "r1",
#     f"echo '{jsonblank}'",
#     jsonbad,
#     "Output json is blank, match json is bad, fail is pass",
#     expect_fail=True,
# )

# _, ret = match_step_json(
#     "r1",
#     f"echo '{jsonbad}'",
#     jsonbad,
#     "Output json and match json are bad, fail is pass",
#     expect_fail=True,
# )

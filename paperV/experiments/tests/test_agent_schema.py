"""The fast action validator agrees with the JSON schema."""
import math

import jsonschema

from agent import ACTION_SCHEMA, validate, actions_for_fleet

N = 4
CASES = [
    ({"uav": 0, "type": "waypoint", "waypoint": [1.0, 2.0]}, True),
    ({"uav": 3, "type": "velocity", "velocity": [0, -3]}, True),
    ({"uav": 1, "type": "mode", "mode": "rtl"}, True),
    ({"uav": 2, "type": "task", "task": 2}, True),
    ({"uav": 4, "type": "mode", "mode": "rtl"}, False),
    ({"uav": 0, "type": "mode", "mode": "land_now"}, False),
    ({"uav": 0, "type": "waypoint"}, False),
    ({"uav": 0, "type": "waypoint", "waypoint": [1.0]}, False),
    ({"uav": 0, "type": "waypoint", "waypoint": [float("nan"), 1.0]}, False),
    ({"uav": 0, "type": "velocity", "velocity": [math.inf, 1.0]}, False),
    ({"uav": 0, "type": "warp", "to": "moon"}, False),
    ({"uav": True, "type": "mode", "mode": "rtl"}, False),
    ({"uav": 0, "type": "mode", "mode": "rtl", "extra": 1}, False),
    ({"uav": 0, "type": "task", "task": 99}, False),
    ("not an action", False),
    (None, False),
]


def test_validator_matches_schema():
    v = jsonschema.Draft202012Validator(ACTION_SCHEMA)
    for a, expect in CASES:
        ok = validate(a, N)[1]
        assert ok == expect, a
        if expect:
            assert v.is_valid(a), a


def test_fleet_parse_failures_counted():
    acts, fails = actions_for_fleet([{"uav": 0, "type": "mode", "mode": "nominal"}, "junk"], N)
    assert len(acts) == N and fails == 1 + 3
    acts, fails = actions_for_fleet("not a list", N)
    assert fails == N and all(a["mode"] == "loiter" for a in acts)

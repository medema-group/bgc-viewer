"""Tests for file_utils."""

import pytest

from bgc_viewer.file_utils import match_location


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("[164:2414](+)", (164, 2414)),
        ("[164:2414]", (164, 2414)),
        ("[<164:>2414](-)", (164, 2414)),
        ("join{[9388:10393](+), [10457:21546](+), [21877:21912](+)}", (9388, 21912)),
        ("join{[300:400](-), [100:200](-)}", (100, 400)),
        ("join{[0:100](+), [200:300](+)}", (0, 300)),
    ],
)
def test_match_location_returns_entire_span(location, expected):
    assert match_location(location) == expected


@pytest.mark.parametrize(
    "location",
    [
        "",
        "invalid",
        "join{[900:1000](+), [0:200](+)}",
        "join{[0:200](-), [900:1000](-)}",
    ],
)
def test_match_location_rejects_locations_without_a_single_span(location):
    assert match_location(location) is None

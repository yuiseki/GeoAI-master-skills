"""uvx --with pytest pytest test_align_time.py

A census every five years (reference 1 October), published about a year later; rows to fill at
several dates. Worked out by hand.
"""

from datetime import date

import pytest

from align_time import asof_join, harmonize, nearest_join

CENSUS = [  # key, reference date, published date, population
    {"key": "X", "ref": date(2015, 10, 1), "pub": date(2016, 10, 26), "value": 100},
    {"key": "X", "ref": date(2020, 10, 1), "pub": date(2021, 11, 30), "value": 110},
]
ROWS = [{"key": "X", "t": date(y, m, 1)} for y, m in ((2019, 6), (2021, 6), (2022, 1))]


def test_joining_on_the_same_year_finds_nothing_for_years_without_a_census():
    years = {(r["key"], r["ref"].year): r["value"] for r in CENSUS}
    assert [years.get((r["key"], r["t"].year)) for r in ROWS] == [None, None, None]


def test_as_of_join_takes_the_latest_value_at_or_before_the_row():
    out = asof_join(ROWS, "t", CENSUS, "ref")
    assert [o["value"] for o in out] == [100, 110, 110]
    assert [o["gap_days"] for o in out] == [(date(2019, 6, 1) - date(2015, 10, 1)).days,
                                            (date(2021, 6, 1) - date(2020, 10, 1)).days,
                                            (date(2022, 1, 1) - date(2020, 10, 1)).days]


def test_a_value_dated_on_the_row_itself_counts_as_known():
    assert asof_join([{"key": "X", "t": date(2020, 10, 1)}], "t", CENSUS, "ref")[0]["value"] == 110


def test_as_of_on_the_publication_date_gives_what_was_known_then():
    # in June 2021 the 2020 census was not yet published: a forecast made then could only use 2015
    out = asof_join(ROWS, "t", CENSUS, "pub")
    assert [o["value"] for o in out] == [100, 100, 110]


def test_as_of_join_respects_a_tolerance_and_leaves_old_values_unmatched():
    out = asof_join(ROWS, "t", CENSUS, "ref", tolerance_days=500)
    assert [o["value"] for o in out] == [None, 110, 110]  # 2019-06 is 1,339 days after 2015-10


def test_nearest_join_can_reach_into_the_future_and_says_so():
    out = nearest_join(ROWS[:1], "t", CENSUS, "ref")
    assert out[0]["value"] == 110 and out[0]["future"]  # 2020-10 is nearer to 2019-06 than 2015-10
    assert asof_join(ROWS[:1], "t", CENSUS, "ref")[0]["value"] == 100


def test_keys_are_never_mixed():
    out = asof_join([{"key": "Y", "t": date(2022, 1, 1)}], "t", CENSUS, "ref")
    assert out[0]["value"] is None


def test_a_merge_sums_old_units_into_the_new_one():
    # A (100) and B (50) merged into C before 2020; C had 160 in 2020
    old = harmonize({"A": 100, "B": 50}, [("A", "C", 1.0), ("B", "C", 1.0)])
    assert old["values"] == {"C": 150}
    assert 160 / old["values"]["C"] - 1 == pytest.approx(0.0667, abs=1e-4)  # not "A fell to 0, C appeared"


def test_a_split_shares_the_old_unit_by_stated_weights():
    r = harmonize({"D": 1000}, [("D", "E", 0.6), ("D", "F", 0.4)])
    assert r["values"] == {"E": pytest.approx(600), "F": pytest.approx(400)}


def test_weights_of_an_old_unit_must_add_up_to_one_and_unmapped_codes_are_listed():
    with pytest.raises(ValueError, match="D"):
        harmonize({"D": 1000}, [("D", "E", 0.6), ("D", "F", 0.3)])
    r = harmonize({"A": 1, "Z": 5}, [("A", "C", 1.0)])
    assert r["unmapped"] == ["Z"] and r["values"] == {"C": 1}

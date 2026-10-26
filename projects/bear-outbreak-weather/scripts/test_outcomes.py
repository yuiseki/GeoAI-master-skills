import datetime as dt

import pandas as pd

import outcomes as oc


def test_parse_month_reads_bare_numbers_and_full_width_digits():
    assert oc.parse_month("０９月") == 9 and oc.parse_month("10") == 10 and oc.parse_month("１０時") is None


def test_autumn_and_whole_year_counts_by_region_and_year():
    df = pd.DataFrame({"year": [2020, 2020, 2020, 2021], "month": [9, 12, 5, None]})
    t = oc.tally(df, "x")
    r2020 = t[t.year == 2020].iloc[0]
    assert r2020.autumn == 2 and r2020.whole == 3
    r2021 = t[t.year == 2021].iloc[0]
    assert r2021.autumn == 0 and r2021.whole == 1  # an unknown month counts in the year, not in the autumn


def test_dedupe_by_date_place_point():
    df = pd.DataFrame({"date": [dt.date(2020, 9, 1)] * 2 + [dt.date(2020, 9, 2)], "place": ["A"] * 3,
                       "lon": [136.5, 136.5000000001, 136.5], "lat": [36.5] * 3})
    assert len(oc.dedupe(df, ["date", "place"])) == 2

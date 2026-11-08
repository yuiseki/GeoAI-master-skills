"""uvx --python 3.12 --with numpy --with pandas --with pytest pytest -q -p no:cacheprovider test_blocks.py"""

# B1-B3 of 02_blocks.py and the period-adjusted difference of 03_within_period.py on small hand-worked tables.
import importlib

import numpy as np
import pandas as pd
import pytest

bl = importlib.import_module("02_blocks")
wp = importlib.import_module("03_within_period")

D1, D2 = pd.Timestamp("1990-07-01"), pd.Timestamp("2005-08-01")


def units(rows):
    return pd.DataFrame(rows, columns=["day", "period", "rain", "utf", "otf"])


# day 1 (first period): >= 70 mm unit 1 under / 3 over, < 70 unit 3 under / 1 over
# day 2 (second):       >= 70 mm unit 0 under / 1 over, < 70 unit 4 under / 0 over
B1_UNITS = [[D1, "first", 80, 1, 3], [D1, "first", 20, 3, 1], [D2, "second", 75, 0, 1], [D2, "second", 10, 4, 0]]


def test_ci_ignores_nan_and_handles_empty():
    assert bl.ci(np.array([np.nan, 1.0, 1.0])) == [1.0, 1.0]
    assert bl.ci(np.array([np.nan])) == [None, None]


def test_diff_at_pooled_and_mean_of_units():
    d = units(B1_UNITS)
    # pooled: >= 70 has 4 over / 5 = 0.8, < 70 has 1 / 8 = 0.125
    assert bl.diff_at(70)(d) == pytest.approx(0.8 - 0.125)
    # mean of unit shares: (3/4 + 1) / 2 - (1/4 + 0) / 2 = 0.875 - 0.125
    assert bl.diff_at(70, mean_of_units=True)(d) == pytest.approx(0.75)


def test_bands_count_units_days_and_buildings():
    b = bl.bands(units(B1_UNITS))
    assert [x["band"] for x in b] == ["0-30", "30-50", "50-70", "70-"]
    assert b[0] == {"band": "0-30", "units": 2, "days": 2, "utf": 7, "otf": 1, "share": 0.125}
    assert b[1]["units"] == 0 and np.isnan(b[1]["share"])
    assert b[3]["units"] == 2 and b[3]["share"] == pytest.approx(0.8)


def test_b1_small_periods_are_undetermined():
    r = bl.b1(units(B1_UNITS))
    assert r["d"] == pytest.approx(0.675)
    assert r["periods"]["first"] == {"d": 0.5, "units_ge": 1, "days_ge": 1}
    assert r["periods"]["second"]["d"] == 1.0
    # dropping day 2 leaves the first period only: 0.5
    assert r["drop_one_day_min"] == 0.5 and r["drop_one_day_min_day"] == "2005-08-01"
    # resampling 2 days: {1,1} -> 0.5, {2,2} -> 1.0, {1,2} -> 0.675; each tail holds a quarter of the draws
    assert r["ci90"] == [0.5, 1.0]
    assert r["ge_cut_otf_top_days"] == {"1990-07-01": 3, "2005-08-01": 1} and r["ge_cut_otf_total"] == 4
    assert r["verdict"] == "undetermined"          # fewer than 5 units at or above 70 mm in a period


def test_b1_verdicts_with_five_units_per_period():
    assert bl.b1(units(B1_UNITS * 5))["verdict"] == "supported"
    flipped = [[d, p, 90 - r if r < 70 else 5, u, o] for d, p, r, u, o in B1_UNITS]   # high rain <-> low rain
    assert bl.b1(units(flipped * 5))["verdict"] == "rejected"


def test_b2_compares_issui_with_naisui_below_50mm_in_wards():
    d = pd.DataFrame([
        [D1, "first", 20, 1, 1, True, "issui"], [D1, "first", 20, 3, 1, True, "naisui"],
        [D2, "second", 20, 0, 2, True, "issui"], [D2, "second", 20, 2, 0, True, "naisui"],
        [D2, "second", 60, 50, 0, True, "issui"],      # >= 50 mm: out
        [D2, "second", 20, 50, 0, False, "issui"],     # not a ward: out
        [D2, "second", 20, 0, 50, True, "other"],      # other reason: out
    ], columns=["day", "period", "rain", "utf", "otf", "ward", "cls"])
    r = bl.b2(d)
    assert r["units"] == {"issui": 2, "naisui": 2}
    assert r["share"]["issui"] == pytest.approx(0.75) and r["share"]["naisui"] == pytest.approx(1 / 6)
    assert r["periods"] == {"first": pytest.approx(0.25), "second": pytest.approx(1.0)}
    assert r["ci90"][0] == pytest.approx(0.25) and r["verdict"] == "supported"


def test_b3_far_gauges_miss_more():
    ge = pd.DataFrame({"day": [D1, D1, D2, D2, D2], "rain": [55, 60, 70, 80, 30], "km": [1, 2, 3, 4, 9],
                       "jma_max1h": [60, 40, 30, 45, 0], "jma_any_max1h": [60, 60, 40, 60, 0]})
    r = bl.b3(ge)
    assert r["events"] == 4 and r["days"] == 2 and r["median_km"] == 2.5     # the 30 mm event is out
    assert r["miss_share"] == 0.75 and r["miss_any_station_share"] == 0.25
    assert r["near"] == {"events": 2, "miss": 0.5} and r["far"] == {"events": 2, "miss": 1.0}
    assert r["d"] == 0.5 and r["gap_mm_median"] == 27.5                     # median of [-5, 20, 40, 35]
    # one-day resamples leave near or far empty (NaN, dropped); mixed ones give 0.5
    assert r["ci90"] == [0.5, 0.5] and r["verdict"] == "supported"


def test_adjusted_weights_the_period_differences():
    d = units(B1_UNITS)
    g = wp.adjusted(bl.diff_at(70), lambda x: int((x["rain"] >= 70).sum()))
    assert g(d) == pytest.approx((0.5 * 1 + 1.0 * 1) / 2)


@pytest.mark.xfail(strict=True, reason="BUG: 03_within_period.adjusted multiplies a period's NaN difference by its "
                                       "weight 0, so one period with no unit at or above the cut makes the whole "
                                       "adjusted difference NaN instead of the other period's difference")
def test_adjusted_ignores_a_period_with_zero_weight():
    d = units([[D1, "first", 80, 1, 3], [D1, "first", 20, 3, 1], [D2, "second", 10, 4, 0]])
    g = wp.adjusted(bl.diff_at(70), lambda x: int((x["rain"] >= 70).sum()))
    assert g(d) == pytest.approx(0.5)

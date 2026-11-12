"""uvx --with pandas --with numpy --with pyarrow --with pytest pytest test_ttr_metrics.py"""

# Tests for ttr_metrics.py: 15-minute bins, the FHWA periods, LOTTR, TTI, PTI, delay and the AM/PM comparison,
# on synthetic links whose travel times are known.

import numpy as np
import pandas as pd
import pytest

from ttr_metrics import bin15, compare_periods, free_flow, metrics, period_of


def test_fhwa_periods():
    ts = pd.to_datetime(["2026-10-05 05:59", "2026-10-05 06:00", "2026-10-05 09:59", "2026-10-05 10:00",
                         "2026-10-05 16:00", "2026-10-05 19:59", "2026-10-05 20:00",
                         "2026-10-04 06:00", "2026-10-04 19:59", "2026-10-04 20:00"])   # 10-05 is a Monday
    assert period_of(ts).tolist() == [None, "AM", "AM", "MIDD", "PM", "PM", None, "WE", "WE", None]


def test_holidays_are_not_weekdays():
    ts = pd.to_datetime(["2026-10-12 07:00"])
    assert period_of(ts, holidays={pd.Timestamp("2026-10-12").date()}).tolist() == ["WE"]


def test_bins_average_within_15_minutes_and_count_the_rows():
    df = pd.DataFrame({"link": ["a"] * 4, "time": pd.to_datetime(["2026-10-05 07:01", "2026-10-05 07:14",
                                                                    "2026-10-05 07:15", "2026-10-05 07:20"]),
                       "travel_time_s": [100.0, 200.0, 300.0, -1.0]})
    b, audit = bin15(df)
    assert b["travel_time_s"].tolist() == [150.0, 300.0]
    assert audit == {"rows": 4, "invalid": 1, "used": 3, "bins": 2}


def week(link, base_tt, am_tts, night_tt):
    """Five weekdays: one AM bin per day with the given travel times, and night bins at night_tt."""
    rows = []
    for d, tt in zip(pd.date_range("2026-10-05", periods=5), am_tts):
        rows.append((link, d + pd.Timedelta(hours=7), tt))
        rows.append((link, d + pd.Timedelta(hours=12), base_tt))
        rows.append((link, d + pd.Timedelta(hours=17), base_tt * 2))
        for h in (1, 2, 3):
            rows.append((link, d + pd.Timedelta(hours=h), night_tt))
    return rows


def test_lottr_is_p80_over_p50_with_linear_interpolation():
    rows = week("a", 100.0, [100, 110, 120, 130, 200], 80.0)
    df = pd.DataFrame(rows, columns=["link", "time", "travel_time_s"])
    b, _ = bin15(df)
    m = metrics(b).set_index(["link", "period"])
    p80 = np.percentile([100, 110, 120, 130, 200], 80)       # 144
    assert m.loc[("a", "AM"), "lottr"] == pytest.approx(p80 / 120)
    assert m.loc[("a", "AM"), "free_flow_s"] == pytest.approx(80.0)
    assert m.loc[("a", "AM"), "tti"] == pytest.approx(np.mean([100, 110, 120, 130, 200]) / 80)
    assert m.loc[("a", "AM"), "pti"] == pytest.approx(np.percentile([100, 110, 120, 130, 200], 95) / 80)
    assert m.loc[("a", "AM"), "delay_s"] == pytest.approx(132 - 80)
    assert m.loc[("a", "PM"), "tti"] == pytest.approx(200 / 80)
    assert m.loc[("a", "AM"), "days"] == 5 and m.loc[("a", "AM"), "bins"] == 5


def test_free_flow_is_the_15th_percentile_of_the_night():
    df = pd.DataFrame({"link": "a", "time": pd.date_range("2026-10-05 00:00", periods=20, freq="15min"),
                       "travel_time_s": np.arange(20, dtype=float) + 50})
    ff = free_flow(bin15(df)[0])
    night = [50 + i for i in range(20)]           # 00:00 to 04:45 are all night
    assert ff["a"] == pytest.approx(np.percentile(night, 15))


def test_compare_am_pm_with_day_bootstrap():
    rows = week("a", 100.0, [100] * 5, 80.0) + week("b", 100.0, [300] * 5, 80.0)
    b, _ = bin15(pd.DataFrame(rows, columns=["link", "time", "travel_time_s"]))
    c = compare_periods(b, "AM", "PM", reps=200, seed=0).set_index("link")
    assert c.loc["a", "diff_s"] == pytest.approx(200 - 100)        # PM minus AM, mean over days
    assert c.loc["b", "diff_s"] == pytest.approx(200 - 300)
    assert c.loc["a", "lo"] == pytest.approx(100) and c.loc["a", "hi"] == pytest.approx(100)


def test_a_link_without_night_data_has_no_free_flow_and_says_so():
    df = pd.DataFrame({"link": "a", "time": pd.to_datetime(["2026-10-05 07:00"]), "travel_time_s": [100.0]})
    m = metrics(bin15(df)[0])
    assert np.isnan(m.loc[0, "tti"]) and m.loc[0, "lottr"] == pytest.approx(1.0)

"""uvx --with pytest --with numpy --with pandas pytest scripts/test_overfloor.py"""
import numpy as np
import pandas as pd

from overfloor import boot_by_day, count, drop_one_day, nearest_station, rain60, share


def test_rain60_reads_the_leading_number():
    assert rain60("68") == 68
    assert rain60("16.5") == 16.5
    assert rain60("16(3)") == 16


def test_rain60_treats_brackets_dashes_and_blank_as_missing():
    for v in ["(280)", "-", "‐", "", None, float("nan"), "不明"]:
        assert rain60(v) is None


def test_count_reads_the_leading_integer_and_zero_otherwise():
    assert count("12(2)") == 12
    assert count("0") == 0
    assert count(None) == 0
    assert count("-") == 0
    assert count(float("nan")) == 0


def test_share_pools_buildings_and_skips_units_without_damage():
    d = pd.DataFrame({"utf": [3, 0, 0], "otf": [1, 0, 4]})
    assert share(d) == 5 / 8
    assert np.isnan(share(d.iloc[1:2]))


def test_boot_by_day_resamples_whole_days():
    # two days; each day's records always travel together, so a statistic equal to the number of distinct
    # (day, record) pairs per drawn day can only take values made of whole days
    d = pd.DataFrame({"day": [1, 1, 2], "v": [1.0, 1.0, 5.0]})
    vals = boot_by_day(d, lambda x: x["v"].sum(), reps=200, seed=0)
    assert set(np.round(vals, 6)) <= {4.0, 7.0, 10.0}  # day1+day1, day1+day2, day2+day2


def test_drop_one_day_returns_one_value_per_day():
    d = pd.DataFrame({"day": [1, 1, 2, 3], "v": [1.0, 2.0, 3.0, 4.0]})
    got = drop_one_day(d, lambda x: x["v"].sum())
    assert got == {1: 7.0, 2: 7.0, 3: 6.0}


def test_nearest_station_skips_stations_without_a_value():
    st = pd.DataFrame({"station_id": ["a", "b"], "lon": [139.70, 139.80], "lat": [35.70, 35.70],
                       "max1h": [np.nan, 30.0]})
    sid, km, v = nearest_station(139.71, 35.70, st)
    assert sid == "b" and v == 30.0
    assert 8 < km < 8.5  # 0.09 degrees of longitude at 35.7 N

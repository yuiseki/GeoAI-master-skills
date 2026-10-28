"""Known-answer tests for the MODIS quality rules and the satellite cues."""

import numpy as np
import pandas as pd
import pytest

import satellite as st


def test_lst_keeps_produced_values_only():
    v = st.lst_c([15000, 15000, 15000, 0], [0, 1, 2, 0])
    assert v[0] == pytest.approx(15000 * 0.02 - 273.15) and v[1] == pytest.approx(v[0])
    assert np.isnan(v[2]) and np.isnan(v[3])
    assert np.isfinite(st.lst_c([15000], [0b11110101]))  # higher bits do not matter, bits 0-1 = 01


def test_npp_fill_and_evi_reliability():
    assert st.npp([5000, 32761]).tolist()[0] == pytest.approx(0.5) and np.isnan(st.npp([32761])[0])
    e = st.evi([4000, 4000, 4000], [0, 1, 2])
    assert e[:2] == pytest.approx([0.4, 0.4]) and np.isnan(e[2])


def test_greenup_is_the_first_day_at_the_midpoint():
    days = [70, 86, 102, 118, 134, 150, 166]
    vals = [0.2, 0.2, 0.3, 0.5, 0.6, 0.6, np.nan]
    assert st.greenup(days, vals, need=6) == 118  # midpoint 0.4
    assert np.isnan(st.greenup(days[:5], vals[:5], need=6))


def test_site_years_need_four_summer_composites_for_s1():
    raw = pd.DataFrame({"ID": [1] * 4 + [2] * 3, "pref": ["A"] * 7, "year": [2005] * 7,
                        "date": pd.to_datetime(["2005-07-01"] * 7), "value": [20, 22, 24, 26, 30, 30, 30.0]})
    sy = st.site_years(raw, "S1")
    assert sy.ID.tolist() == [1] and sy.value.iloc[0] == pytest.approx(23)


def test_prefecture_anomaly_uses_2001_2010():
    sy = pd.DataFrame({"ID": [1] * 11, "pref": ["A"] * 11, "year": list(range(2001, 2012)),
                       "value": [1.0] * 10 + [3.0]})
    p = st.prefecture_cue(sy, "S2")
    assert p[p.year == 2011].S2.iloc[0] == pytest.approx(2.0) and p.S2_sites.max() == 1


def test_latest_versions_keeps_one_copy_per_tile_and_date():
    jobs = [("MOD17A3HGF.A2013001.h28v04.061.2021300165158", None, {}),
            ("MOD17A3HGF.A2013001.h28v04.061.2021324233025", None, {}),
            ("MOD17A3HGF.A2013001.h28v05.061.2021306132605", None, {})]
    kept = [j[0] for j in st.latest_versions(jobs)]
    assert kept == ["MOD17A3HGF.A2013001.h28v04.061.2021324233025", "MOD17A3HGF.A2013001.h28v05.061.2021306132605"]


def test_lagged_moves_values_to_the_next_target_year():
    import satellite_b5 as sb

    sat = pd.DataFrame({"pref": ["A", "A"], "year": [2008, 2009], "S1": [1.0, 2.0]})
    out = sb.lagged(sat, ["S1"], 1)
    assert out.columns.tolist() == ["pref", "year", "S1_t-1"] and out.year.tolist() == [2009, 2010]

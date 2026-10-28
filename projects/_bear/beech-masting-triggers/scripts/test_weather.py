"""Known-answer tests for the weather cues."""

import pandas as pd
import pytest

import weather as wx


def frame(years, tmax_jul_aug, tmin_apr_may, pref="秋田県"):
    rows = []
    for y, tx, tn in zip(years, tmax_jul_aug, tmin_apr_may):
        for mo in range(1, 13):
            rows.append({"pref": pref, "year": y, "month": mo,
                         "tmax_c": tx if mo in (7, 8) else 0.0, "tmin_c": tn if mo in (4, 5) else -10.0})
    return pd.DataFrame(rows)


def test_cues_are_anomalies_from_the_1981_2010_mean():
    years = list(range(1981, 2012))
    m = frame(years, [25.0] * 30 + [27.0], [5.0] * 30 + [4.0])
    c = wx.cues(m)
    last = c[c.year == 2011].iloc[0]
    assert last.Ts == pytest.approx(2.0) and last.Tsp == pytest.approx(-1.0)
    assert last.Ts_raw_c == pytest.approx(27.0)
    assert c[c.year == 1990].Ts.iloc[0] == pytest.approx(0.0)


def test_a_missing_summer_month_stops():
    m = frame(list(range(1981, 2011)), [25.0] * 30, [5.0] * 30)
    m = m[~((m.year == 1995) & (m.month == 8))]
    with pytest.raises(ValueError):
        wx.cues(m)


def test_the_last_year_without_its_summer_yet_is_left_out():
    m = frame(list(range(1981, 2012)), [25.0] * 31, [5.0] * 31)
    m = m[~((m.year == 2011) & (m.month >= 8))]
    c = wx.cues(m)
    assert c[c.year == 2011].Ts.isna().all() and c[c.year == 2011].Tsp.notna().all()

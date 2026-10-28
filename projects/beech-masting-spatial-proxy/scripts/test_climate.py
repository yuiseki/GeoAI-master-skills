import numpy as np
import pandas as pd
import pytest

import climate as C


def monthly(ids=(1, 2), years=range(1979, 2011)):
    rows = []
    for i in ids:
        for y in years:
            for m in range(1, 13):
                rows.append({"ID": i, "year": y, "month": m, "tmax_c": 10.0 * i + m + (y - 1995) * 0.1,
                             "tmin_c": i + m, "precip_mm": 100.0 + m, "et0_mm": 50.0 + m})
    return pd.DataFrame(rows)


def test_seasons_and_anomalies():
    out = C.site_year(monthly())
    r = out[(out.ID == 2) & (out.year == 2000)].iloc[0]
    # Ts = mean of Jul and Aug tmax; the 1981-2010 mean of the trend term (y - 1995) * 0.1 is 0.05
    assert r.Ts_raw_c == pytest.approx(20 + 7.5 + 0.5)
    assert r.Ts == pytest.approx(0.45)
    assert r.Tsp_raw_c == pytest.approx(2 + 4.5)
    assert r.P_raw_mm == pytest.approx(300 + 6 + 7 + 8)  # June-August sum
    assert r.PET_raw_mm == pytest.approx(150 + 21)
    assert r.Tsp == pytest.approx(0.0) and r.P == pytest.approx(0.0) and r.PET == pytest.approx(0.0)


def test_missing_month_stops():
    m = monthly()
    m.loc[(m.ID == 1) & (m.year == 1990) & (m.month == 7), "tmax_c"] = np.nan
    with pytest.raises(ValueError):
        C.site_year(m)
    m = monthly().query("not (ID == 1 and year == 1990 and month == 8)")
    with pytest.raises(ValueError):
        C.site_year(m)

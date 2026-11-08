"""uvx --python 3.12 --with numpy --with scipy --with pandas --with pytest pytest -q -p no:cacheprovider test_explore_weather.py"""

# summer_series and lagged of explore_weather.py.
import numpy as np
import pandas as pd

from explore_weather import lagged, summer_series


def test_summer_series_means_solar_and_sums_precipitation_per_region_year():
    sp = pd.DataFrame({
        "region": ["akita"] * 5 + ["iwate"],
        "date": ["2020-06-01", "2020-07-01", "2020-08-31", "2020-06-01", "2020-07-01", "2021-06-01"],
        "short_id": ["AGERA5-SRF", "AGERA5-SRF", "AGERA5-SRF", "AGERA5-PF-M", "AGERA5-PF-M", "AGERA5-SRF"],
        "value": [10.0, 20.0, 30.0, 100.0, 50.0, 7.0],
    })
    w = summer_series(sp).set_index(["region", "year"])
    assert w.loc[("akita", 2020), "SRF"] == 20.0 and w.loc[("akita", 2020), "srf_days"] == 3
    assert w.loc[("akita", 2020), "P"] == 150.0 and w.loc[("akita", 2020), "p_months"] == 2
    # outer join: a region-year with solar but no precipitation keeps NaN for P
    assert np.isnan(w.loc[("iwate", 2021), "P"]) and w.loc[("iwate", 2021), "SRF"] == 7.0


def test_lagged_shifts_within_each_region_in_year_order():
    df = pd.DataFrame({"region": ["b", "a", "a", "b", "a"], "year": [2021, 2022, 2020, 2020, 2021],
                       "T": [21.0, 32.0, 30.0, 20.0, 31.0]})
    out = lagged(df, "T").set_index(["region", "year"])
    assert out.loc[("a", 2022), "T_now"] == 32.0 and out.loc[("a", 2022), "T_last"] == 31.0
    assert out.loc[("a", 2022), "T_last2"] == 30.0
    assert np.isnan(out.loc[("a", 2020), "T_last"]) and np.isnan(out.loc[("a", 2021), "T_last2"])
    assert out.loc[("b", 2021), "T_last"] == 20.0                 # never the other region's value

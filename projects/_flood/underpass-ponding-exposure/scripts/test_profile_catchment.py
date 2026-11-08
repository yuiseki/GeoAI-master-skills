"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with pandas --with shapely --with pytest pytest -q -p no:cacheprovider test_profile_catchment.py"""

# catchment of 04_profile.py with a stand-in for dem.Tiles, and crosstab of 09_mt_blocks.py.
import importlib

import numpy as np
import pandas as pd

p4 = importlib.import_module("04_profile")
mt = importlib.import_module("09_mt_blocks")


class FakeTiles:
    """Gives back a fixed window with the point in its centre pixel."""
    z, size = 16, 256

    def __init__(self, win, m):
        self.win, self.m = win, m

    def window(self, lon, lat, radius_m):
        r = self.win.shape[0] // 2
        return self.win, self.m, r, r


def bowl(n=11):
    yy, xx = np.indices((n, n))
    c = n // 2
    return np.hypot(yy - c, xx - c)


def test_catchment_of_a_single_bowl_is_the_whole_window():
    # every pixel descends to the centre, which is the bottom: 11 x 11 pixels of 5 m x 5 m
    assert p4.catchment(FakeTiles(bowl(), 5.0), 139.7, 35.7, 139.7, 35.7) == 121 * 25.0


def test_catchment_leaves_out_a_second_basin_beyond_the_pit_radius():
    a = bowl()
    a[:, 8:] = 20 - np.arange(3)[None, :]            # a ridge at 20, 19, 18 m in columns 8-10
    # Column 8 falls more steeply west into the bowl than east (to 19 m), so it joins the bowl; columns 9-10 drain
    # to column 10, more than 15 m (3 pixels of 5 m) from the bottom, and are left out: 11 x 9 pixels.
    got = p4.catchment(FakeTiles(a, 5.0), 139.7, 35.7, 139.7, 35.7)
    assert got == 11 * 9 * 25.0


def test_catchment_none_when_most_of_the_window_is_missing():
    a = bowl()
    a[:6] = np.nan
    assert p4.catchment(FakeTiles(a, 5.0), 139.7, 35.7, 139.7, 35.7) is None


def test_crosstab_of_dem5a_and_mapterhorn_dips():
    rows = pd.DataFrame({
        "depth_5a_100": [3.0, 3.0, 1.0, 1.0, np.nan, np.nan, 2.0],
        "depth_mt_100": [2.5, 0.5, 2.0, 0.0, 4.0, 1.0, np.nan],
        "ok_5a_100": [True] * 7,
        "ok_mt_100": [True] * 6 + [False],
        "matched": [True] * 6 + [True],
    })
    assert mt.crosstab(rows, "depth") == {"measurable_both": 4, "dip_both": 1, "dip_5a_only": 1, "dip_mt_only": 1,
                                          "dip_neither": 1, "mt_measurable_where_5a_not": 2,
                                          "mt_dip_where_5a_not_measurable": 1}

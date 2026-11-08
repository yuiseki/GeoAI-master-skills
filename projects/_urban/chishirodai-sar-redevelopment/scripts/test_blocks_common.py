"""uvx --python 3.12 --with numpy --with scipy --with pyproj --with rasterio --with pillow --with pytest pytest -q -p no:cacheprovider test_blocks_common.py"""

# common.py (tile bounds, analysis box), the observables of 04_blocks.py, and the web-mercator helpers of 08_site_sar.py.
import importlib
import math
import os

for _k in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA"):    # an anaconda proj.db breaks rasterio (see the scripts' env -u)
    os.environ.pop(_k, None)

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import common  # noqa: E402
from rank import tile_xy  # noqa: E402

bk = importlib.import_module("04_blocks")
ss = importlib.import_module("08_site_sar")


def test_tile_bounds_contain_the_site():
    w, s, e, n = common.tile_lonlat_bounds(58289, 25820)
    lon, lat = common.SITE
    assert w <= lon < e and s <= lat < n
    assert e - w == pytest.approx(360 / 2 ** 16)
    assert tile_xy(lon, lat, 16) == (58289, 25820)


def test_box_lonlat_spans_the_12_by_12_tiles_and_box_utm_covers_it():
    w, s, e, n = common.box_lonlat()
    assert e - w == pytest.approx(12 * 360 / 2 ** 16)
    assert (w, n) == pytest.approx(common.tile_lonlat_bounds(58284, 25815)[0::3])
    x0, y0, x1, y1 = common.box_utm()
    assert all(v % 10 == 0 for v in (x0, y0, x1, y1))
    b0, b1, b2, b3 = common.box_utm(margin=0)
    assert x0 <= b0 - 190 and x1 >= b2 + 190 and y0 <= b1 - 190 and y1 >= b3 + 190


def test_ordinal():
    assert bk.ordinal("2020-03-01") - bk.ordinal("2020-02-28") == 2


def test_a_observables_takes_the_strongest_darkening_inside_the_window():
    dates = ["2019-01-01", "2020-01-01", "2021-01-01", "2026-01-01"]          # the first and last are outside W
    change = np.array([[0, 1, 0], [1, 0, 0], [1, 0, 1], [0, 0, 0]], bool)
    ratio = np.array([[0, -4, 0], [-3, 0, 0], [-5, 0, 2], [0, 0, 0]], float)
    a = bk.a_observables({"change": change, "ratio_db": ratio}, dates, np.array([True, True, False]))
    # pixel 0 darkens in 2020 (-3 dB) and 2021 (-5 dB): 2021; pixel 1 only before W; the control only brightens
    assert a == {"p_site": 0.5, "p_ctrl": 0.0, "ratio": None, "D_sar": "2021-01-01", "D_sar_q1": "2021-01-01",
                 "D_sar_q3": "2021-01-01", "site_pixels_with_dark": 1}


def test_tile_scores_share_of_changed_valid_pixels():
    key = np.array(["a", "a", "a", "b", "c"])
    changed = np.array([1, 0, 1, 1, 0], bool)
    valid = np.array([1, 1, 0, 1, 0], bool)
    s = bk.tile_scores(changed, valid, key, ["a", "b", "c"])
    assert s["a"] == 0.5 and s["b"] == 1.0 and math.isnan(s["c"])


def test_b_observables_recall_against_built_up_share():
    site = bk.SITE_TILE
    ids = [site] + [f"t{i}" for i in range(9)]
    labels = {i: "0" for i in ids}
    labels.update({site: "2", "t0": "2", "t1": "1"})
    score = {i: 0.01 * k for k, i in enumerate(ids)}
    score.update({site: 0.9, "t1": 0.8, "t0": 0.0})
    built = {i: 0.0 for i in ids}
    built.update({"t0": 0.9, "t5": 0.8})
    b = bk.b_observables(score, ids, labels, built)
    assert (b["tiles"], b["k"], b["positives_2"], b["hits_2"]) == (10, 2, 2, 1)
    assert (b["recall_2_sar"], b["recall_2_builtup"], b["diff"]) == (0.5, 0.5, 0.0)
    assert (b["recall_12_sar"], b["recall_12_builtup"]) == (0.6667, 0.3333)
    # P(at least 1 of the 2 positives in 2 random draws of 10) = 1 - C(8,2)/C(10,2) = 17/45
    assert b["p_random_at_least_hits"] == round(17 / 45, 6)
    assert b["site_rank"] == 1 and b["top_k_labels"] == {"0": 0, "1": 1, "2": 1}
    bx = bk.b_observables(score, ids, labels, built, exclude=(site,))
    assert bx["tiles"] == 9 and bx["site_rank"] is None and bx["positives_2"] == 1


def test_site_sar_mercator_helpers():
    assert ss.merc_x(2 ** ss.Z / 2) == pytest.approx(0.0) and ss.merc_y(2 ** ss.Z / 2) == pytest.approx(0.0, abs=1e-6)
    assert ss.merc_x(0) == pytest.approx(-math.pi * ss.R)
    # the site falls in the middle tile of the 3 x 3 window: pixel 256..512 on both axes
    px, py = ss.pixel(*common.SITE)
    assert 256 <= px < 512 and 256 <= py < 512
    assert tile_xy(*common.SITE, ss.Z) == (ss.CX, ss.CY)

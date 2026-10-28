"""Tests for the per-pixel QA, the 300 m disk and the per-acquisition aggregation (landsat.py)."""

import numpy as np
import pandas as pd
from affine import Affine

import landsat as L

CLEAR = 5440  # clear bit + low confidences, as on clear forest pixels


def test_disk_keeps_pixel_centres_within_radius():
    t = Affine(30.0, 0, 1000.0, 0, -30.0, 2000.0)
    win, dx, dy, inside = L.disk(t, 1000.0 + 30 * 50 + 15, 2000.0 - 30 * 50 - 15, 300.0)
    assert inside.sum() == np.sum(np.hypot(dx, dy) <= 300.0)
    # site on a pixel centre: 21 x 21 window holds the disk, the centre pixel is at distance 0
    assert dx.shape == (L.HALF * 2 + 1, L.HALF * 2 + 1)
    assert np.isclose(np.hypot(dx, dy).min(), 0.0)
    assert 300 <= inside.sum() <= 330
    assert win.col_off == 50 - L.HALF and win.row_off == 50 - L.HALF


def test_qa_reasons_follow_collection_2_bits():
    qa = np.array([CLEAR, 1, CLEAR | 2, CLEAR | 8, CLEAR | 16, CLEAR | 32, CLEAR | 128, CLEAR, CLEAR, CLEAR])
    rad = np.array([0, 0, 0, 0, 0, 0, 0, 1 << 3, 1 << 9, 1 << 0])
    sr = np.full(10, 10000)
    sr_bad = sr.copy()
    r = L.reasons(qa, rad, sr, sr, sr)
    assert r["fill"].tolist() == [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    assert r["cloud"].tolist() == [0, 0, 1, 1, 0, 0, 0, 0, 0, 0]  # dilated or high-confidence cloud
    assert r["shadow"].tolist()[4] == 1 and r["snow"].tolist()[5] == 1
    assert r["saturated"].tolist() == [0, 0, 0, 0, 0, 0, 0, 1, 1, 0]  # band 4 and dropped; band 1 not used
    assert r["water"].tolist()[6] == 1
    assert r["valid"].tolist() == [1, 0, 0, 0, 0, 0, 1, 0, 0, 1]  # water is kept
    sr_bad[0] = 7000
    assert L.reasons(qa, rad, sr_bad, sr, sr)["out_of_range"][0] == 1
    assert L.reasons(qa, rad, sr_bad, sr, sr)["valid"][0] == 0


def test_aggregate_takes_medians_of_per_pixel_indices():
    red = np.array([8000, 8000, 9000, 0])
    nir = np.array([20000, 22000, 24000, 0])
    swir = np.array([14000, 15000, 16000, 0])
    qa = np.array([CLEAR, CLEAR, CLEAR | 8, 1])
    rad = np.zeros(4, int)
    a = L.aggregate(red, nir, swir, qa, rad)
    assert a["n_pixels"] == 4 and a["n_valid"] == 2 and a["n_cloud"] == 1 and a["n_fill"] == 1
    sr = lambda d: d * 0.0000275 - 0.2  # noqa: E731
    nd = [(sr(n) - sr(r)) / (sr(n) + sr(r)) for n, r in ((20000, 8000), (22000, 8000))]
    assert np.isclose(a["ndvi"], np.median(nd))
    assert np.isclose(a["red"], sr(8000))
    nm = [(sr(n) - sr(s)) / (sr(n) + sr(s)) for n, s in ((20000, 14000), (22000, 15000))]
    assert np.isclose(a["ndmi"], np.median(nm))


def test_aggregate_with_no_valid_pixel_is_missing_not_zero():
    a = L.aggregate(np.zeros(3), np.zeros(3), np.zeros(3), np.ones(3, int), np.zeros(3, int))
    assert a["n_valid"] == 0 and np.isnan(a["ndvi"]) and np.isnan(a["ndmi"])


def test_dedupe_keeps_more_valid_pixels_then_smaller_id():
    df = pd.DataFrame({"ID": [1, 1, 1, 2], "date": ["1999-08-10"] * 3 + ["1999-08-10"],
                       "item_id": ["b", "a", "c", "a"], "n_valid": [300, 300, 10, 5]})
    out = L.dedupe(df)
    assert sorted(zip(out.ID, out.item_id)) == [(1, "a"), (2, "a")]

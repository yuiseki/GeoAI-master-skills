"""uvx --python 3.12 --with numpy --with scipy --with pytest pytest -q scripts/test_water_stats.py"""

import numpy as np
import pytest

from water_stats import best_shift, pair_dates, pond_fractions, shifted, twoway_resid


def test_best_shift_recovers_a_known_offset():
    rng = np.random.default_rng(0)
    mask = np.zeros((80, 80), bool)
    mask[20:30, 15:40] = True
    mask[50:70, 50:60] = True
    img = np.zeros((80, 80))
    img[22:32, 18:43] = 1.0                    # the image is the mask moved 2 rows down, 3 columns right
    img[52:72, 53:63] = 1.0
    img += rng.normal(0, 0.1, img.shape)
    s, c = best_shift(mask, img, r=5)
    assert s == (2, 3) and c > 0.9
    back = shifted(img, s)
    assert np.nanmean(back[mask]) > 0.9 and np.nanmean(back[~mask]) < 0.1


def test_shifted_marks_the_cells_that_leave_the_grid():
    img = np.arange(16.0).reshape(4, 4)
    out = shifted(img, (1, 0))
    assert np.isnan(out[3]).all() and out[0, 0] == img[1, 0]


def test_pond_fractions_count_valid_pixels_only():
    labels = np.array([[1, 1, 2, 2], [1, 1, 2, 0]])
    valid = np.array([[1, 1, 1, 0], [1, 0, 1, 1]], bool)
    water = np.array([[1, 0, 1, 1], [1, 1, 0, 1]], bool)
    n, f = pond_fractions(labels, valid, water, [1, 2, 3])
    assert n.tolist() == [3, 2, 0]
    assert f[0] == pytest.approx(2 / 3) and f[1] == pytest.approx(0.5) and np.isnan(f[2])


def test_twoway_resid_removes_pond_and_date_effects():
    rng = np.random.default_rng(1)
    pond = np.repeat(np.arange(30), 8)
    day = np.tile(np.arange(8), 30)
    keep = rng.random(pond.size) > 0.2          # unbalanced
    pond, day = pond[keep], day[keep]
    signal = rng.normal(0, 1, pond.size)
    x = 5 * rng.normal(size=30)[pond] + 3 * rng.normal(size=8)[day] + signal
    r = twoway_resid(x, pond, day)
    for g in (pond, day):
        assert np.allclose(np.bincount(g, weights=r), 0, atol=1e-8)
    assert np.corrcoef(r, signal)[0, 1] > 0.9


def test_pair_dates_take_the_nearest_within_the_window():
    got = pair_dates(["2024-07-02", "2024-07-14", "2024-07-26"], ["2024-07-01", "2024-07-04", "2024-07-17", "2024-07-29"])
    assert got == {"2024-07-02": "2024-07-01"}  # 07-14 and 07-26 are 3 days from the nearest


def test_best_shift_can_ignore_a_large_dark_area_far_from_the_ponds():
    rng = np.random.default_rng(2)
    mask = np.zeros((100, 100), bool)
    mask[20:28, 20:30] = True
    mask[40:46, 60:70] = True
    img = rng.normal(0, 0.1, (100, 100))
    img[21:29, 22:32] += 1.0                      # ponds moved 1 row, 2 columns
    img[41:47, 62:72] += 1.0
    img[70:, :] += 1.0                            # a sea: as bright as the ponds, not in the mask
    near = np.zeros_like(mask)
    near[10:60, 10:80] = True
    s_all, c_all = best_shift(mask, img, r=4)
    s_near, c_near = best_shift(mask, img, r=4, where=near)
    assert s_near == (1, 2) and c_near > c_all

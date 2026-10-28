"""Tests for greedy high-score seed dilation under a hard area budget."""

import numpy as np
import pytest

import fixed_area_dilation as dilation
import metrics as mt


def test_radius_100_uses_cross_and_stops_without_skipping_oversized_next_seed():
    mask = np.ones((7, 7), dtype=bool)
    iy, ix = np.nonzero(mask)
    center = 3 * 7 + 3
    far = 0
    near = 3 * 7 + 4
    order = np.array([center, far, near] + [i for i in range(49) if i not in (center, far, near)])
    selected, info = dilation.greedy_union(order, ix, iy, mask, radius_m=100,
                                           size_m=100, budget_cells=5)
    expected = np.zeros_like(mask)
    expected[3, 3] = expected[2, 3] = expected[4, 3] = True
    expected[3, 2] = expected[3, 4] = True
    np.testing.assert_array_equal(selected, expected)
    assert info["selected_cells"] == 5
    assert info["accepted_seeds"] == 1
    assert info["stopped_at_rank"] == 1  # far seed would exceed; near seed not tried


def test_euclidean_disk_radius_300_and_prefecture_clip():
    mask = np.ones((9, 9), dtype=bool)
    mask[4, 7] = False  # exactly 300 m east, but outside prefecture
    iy, ix = np.nonzero(mask)
    center_index = int(np.flatnonzero((ix == 4) & (iy == 4))[0])
    order = np.r_[center_index, np.delete(np.arange(len(ix)), center_index)]
    selected, info = dilation.greedy_union(order, ix, iy, mask, radius_m=300,
                                           size_m=100, budget_cells=28)
    assert info["selected_cells"] == 28
    assert selected[4, 7] == 0
    assert selected[4, 6] == 1  # 200 m
    assert selected[6, 6] == 1  # sqrt(8)*100 m
    assert selected[7, 7] == 0  # sqrt(18)*100 m


def test_exact_radius_zero_selects_top_cells_to_budget():
    mask = np.ones((1, 20), dtype=bool)
    iy, ix = np.nonzero(mask)
    order = np.arange(19, -1, -1)
    selected, info = dilation.greedy_union(order, ix, iy, mask, radius_m=0,
                                           size_m=100, budget_cells=1)
    assert int(selected.sum()) == 1
    assert selected[0, 19]
    assert info["stopped_at_rank"] == 1


def test_budget_and_alignment_validation():
    mask = np.ones((3, 3), dtype=bool)
    iy, ix = np.nonzero(mask)
    with pytest.raises(ValueError, match="budget"):
        dilation.greedy_union(np.arange(9), ix, iy, mask, radius_m=100,
                              size_m=100, budget_cells=10)
    with pytest.raises(ValueError, match="aligned"):
        dilation.greedy_union(np.arange(9), ix[:-1], iy, mask, radius_m=100,
                              size_m=100, budget_cells=5)


def test_evaluation_reproduces_exact_reference_and_never_exceeds_five_percent():
    mask = np.ones((10, 20), dtype=bool)
    score = np.arange(200, 0, -1, dtype=float)
    positive = np.zeros(200, dtype=bool)
    positive[[0, 1, 20, 100]] = True
    exact = mt.capture(mt.rank_order(score, seed=0), positive, 0.05)
    result = dilation.evaluate_saved(score, positive, mask, size_m=100,
                                     expected_exact_capture=exact)
    assert result["max_selected_cells"] == 10
    assert [r["radius_m"] for r in result["results"]] == [0, 100, 300, 500]
    assert result["results"][0]["capture"] == exact
    assert all(r["selected_cells"] <= 10 for r in result["results"])
    assert all(r["selected_fraction"] <= 0.05 for r in result["results"])
    with pytest.raises(ValueError, match="did not reproduce"):
        dilation.evaluate_saved(score, positive, mask, size_m=100,
                                expected_exact_capture=-1.0)

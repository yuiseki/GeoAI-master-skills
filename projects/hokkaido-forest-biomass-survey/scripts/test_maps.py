"""Synthetic checks for the cell-grid maps."""

import numpy as np
import pytest

from maps import fit_grid, grid_array, classify


def records(points):
    return [{"cell_row": r, "cell_col": c, "lon": lon, "lat": lat, "v": v}
            for r, c, lon, lat, v in points]


def test_fit_grid_recovers_cell_edges():
    step = 2 / 225
    pts = [(r, c, 143 + (c + 0.5) * step, 46 - (r + 0.5) * step, 0) for r, c in [(1, 1), (3, 4), (2, 7)]]
    grid = fit_grid(records(pts))
    assert grid["step"] == pytest.approx(step)
    assert grid["extent"] == pytest.approx([143 + step, 143 + 8 * step, 46 - 4 * step, 46 - step])


def test_fit_grid_stops_when_centres_are_off_grid():
    step = 2 / 225
    pts = [(1, 1, 143 + 1.5 * step, 46 - 1.5 * step, 0), (2, 2, 143 + 2.5 * step + 0.001, 46 - 2.5 * step, 0)]
    with pytest.raises(ValueError):
        fit_grid(records(pts))


def test_grid_array_leaves_missing_cells_as_nan():
    step = 2 / 225
    pts = [(1, 1, 143 + 1.5 * step, 46 - 1.5 * step, 5.0), (2, 2, 143 + 2.5 * step, 46 - 2.5 * step, -3.0)]
    recs = records(pts)
    grid = fit_grid(recs)
    arr = grid_array(recs, grid, lambda r: r["v"])
    assert arr.shape == (2, 2)
    assert arr[0, 0] == 5.0 and arr[1, 1] == -3.0
    assert np.isnan(arr[0, 1]) and np.isnan(arr[1, 0])


def test_classify_keeps_nan_and_uses_right_open_bins():
    breaks = [-10, 0, 10]
    out = classify(np.array([-20, -10, -0.1, 0, 9.9, 10, 30, np.nan]), breaks)
    assert out[:7].tolist() == [0, 1, 1, 2, 2, 3, 3]
    assert np.isnan(out[7])


def test_municipality_of_lists_every_overlapping_polygon():
    from shapely.geometry import box
    from maps import municipality_of

    munis = [("A町", box(0, 0, 1, 1)), ("B村", box(0.9, 0, 2, 1)), ("C市", box(5, 5, 6, 6))]
    assert municipality_of(0.5, 0.5, munis) == "A町"
    assert municipality_of(0.95, 0.5, munis) == "A町/B村"
    assert municipality_of(3, 3, munis) == ""

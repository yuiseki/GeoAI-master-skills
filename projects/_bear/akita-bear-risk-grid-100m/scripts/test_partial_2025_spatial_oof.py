"""2025 April–September label window and fixed-grid reconciliation."""

import numpy as np
import pytest

from grid import Grid
import partial_2025_spatial_oof as partial


def test_window_uses_observed_at_and_existing_cell_assignment():
    grid = Grid(0, 0, 3, 1, 100)
    muni = np.array([[0, 0, -1]])
    timestamps = np.array([
        "2025-04-01T00:00", "2025-09-30T23:59", "2025-10-01T00:00",
        "2026-01-05T12:00", "2025-08-01T12:00",
    ], dtype="datetime64[m]")
    x = np.array([10, 150, 150, 10, 250])
    y = np.array([10, 10, 10, 10, 10])
    full = np.array([[2, 2, 0]])
    counts, info = partial.seasonal_counts(grid, muni, x, y, timestamps, full)
    np.testing.assert_array_equal(counts, [[1, 1, 0]])
    assert info["n_full_reports"] == 5
    assert info["n_window_reports"] == 3
    assert info["n_window_outside_prefecture_cells"] == 1
    assert info["n_window_positive_cells"] == 2


def test_mismatch_to_existing_full_year_label_stops_before_training():
    grid = Grid(0, 0, 2, 1, 100)
    muni = np.array([[0, 0]])
    timestamps = np.array(["2025-04-01T00:00"], dtype="datetime64[m]")
    with pytest.raises(ValueError, match="full-year"):
        partial.seasonal_counts(grid, muni, np.array([10]), np.array([10]),
                                timestamps, np.array([[0, 0]]))


def test_source_period_excludes_other_bear_years():
    grid = Grid(0, 0, 2, 1, 100)
    muni = np.array([[0, 0]])
    timestamps = np.array(["2025-03-31T23:59"], dtype="datetime64[m]")
    with pytest.raises(ValueError, match="2025 fiscal year"):
        partial.seasonal_counts(grid, muni, np.array([10]), np.array([10]),
                                timestamps, np.array([[0, 0]]))

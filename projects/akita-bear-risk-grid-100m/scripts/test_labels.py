import datetime as dt

import numpy as np

import labels as lb
from grid import Grid


def test_bear_year_runs_from_april_to_march():
    ts = np.array(["2023-03-31T23:59", "2023-04-01T00:00", "2025-12-31T10:00", "2026-01-05T00:00"], dtype="datetime64[m]")
    assert list(lb.bear_year(ts)) == [2022, 2023, 2025, 2025]


def test_counts_by_year_put_points_in_cells_and_count_the_ones_off_the_prefecture():
    g = Grid(0, 0, 3, 1, 100)
    muni = np.array([[0, 0, -1]])
    x = np.array([10, 20, 150, 250, 999])
    y = np.array([10, 10, 10, 10, 10])
    years = np.array([2022, 2023, 2023, 2023, 2023])
    counts, off = lb.counts_by_year(g, muni, x, y, years, [2022, 2023])
    assert counts[2022][0, 0] == 1 and counts[2023][0, 0] == 1 and counts[2023][0, 1] == 1
    assert counts[2023][0, 2] == 0  # the cell is outside the prefecture: not counted as a label
    assert off == {2022: 0, 2023: 2}

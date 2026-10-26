import datetime as dt

import numpy as np
import pandas as pd

import labels_region as lr
from grid import Grid


def test_dedupe_keeps_one_row_per_date_place_and_point():
    df = pd.DataFrame({
        "date": [dt.date(2020, 5, 1)] * 3 + [dt.date(2020, 5, 2)],
        "place": ["A", "A", "B", "A"],
        "lon": [136.5, 136.5, 136.5, 136.5], "lat": [36.5, 36.5, 36.5, 36.5],
    })
    out = lr.dedupe(df, ["date", "place"])
    assert len(out) == 3  # the two identical rows become one; another place or another day stay


def test_dedupe_treats_coordinates_equal_to_six_decimals():
    df = pd.DataFrame({"date": [dt.date(2020, 5, 1)] * 2, "place": ["A", "A"],
                       "lon": [136.5, 136.5000000001], "lat": [36.5, 36.5]})
    assert len(lr.dedupe(df, ["date", "place"])) == 1


def test_counts_put_points_in_cells_and_count_the_rest():
    g = Grid(0, 0, 3, 1, 100)
    lab = np.array([[0, 0, -1]])
    pts = pd.DataFrame({"x": [10, 20, 150, 250, 999], "y": [10, 10, 10, 10, 10], "period": [1, 2, 2, 2, 2]})
    total, by, off = lr.counts(g, lab, pts)
    assert total[0, 0] == 2 and total[0, 1] == 1 and total[0, 2] == 0
    assert by[2][0, 0] == 1 and by[1][0, 0] == 1
    assert off == 2  # one in a cell outside the area, one off the grid

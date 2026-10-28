"""Tests for the rows (rows.py): dT as in beech-masting-spatial-proxy, own lag, the rank-year cut for B2."""

import numpy as np
import pandas as pd
import pytest

import rows as R


def climate():
    years = range(1985, 2009)
    return pd.DataFrame([{"ID": i, "year": y, "Ts": float(y - 1985 + i)} for i in (5, 6) for y in years])


def test_delta_t_is_previous_minus_two_years_before():
    d = R.delta_t(climate()).set_index(["ID", "t"]).dT
    assert d[(5, 2000)] == 1.0 and len(d) == 2 * len(R.TARGETS)


def test_build_lag_and_rank_cut():
    ranks = pd.DataFrame({"ID": [5, 5, 5, 6], "year": [1998, 1999, 2000, 2000], "rank": [1.0, 2.0, 3.0, 0.0]})
    sites = pd.DataFrame({"ID": [5, 6], "x": [0.0, 1.0], "y_m": [0.0, 0.0]})
    rows, r = R.build(ranks, climate(), sites)
    got = rows.set_index(["ID", "t"])
    assert got.loc[(5, 2000), "lag_own"] == 2.0 and np.isnan(got.loc[(6, 2000), "lag_own"])
    rows_dev, r_dev = R.build(ranks, climate(), sites, max_rank_year=1999)
    assert rows_dev.t.max() == 1999 and r_dev.year.max() == 1999


def test_build_refuses_a_row_without_dt():
    ranks = pd.DataFrame({"ID": [7], "year": [2000], "rank": [1.0]})
    sites = pd.DataFrame({"ID": [7], "x": [0.0], "y_m": [0.0]})
    with pytest.raises(ValueError):
        R.build(ranks, climate(), sites)

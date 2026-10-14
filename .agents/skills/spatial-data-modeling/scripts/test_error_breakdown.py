"""uvx --with numpy --with duckdb --with pytest pytest test_error_breakdown.py"""

import numpy as np
import pytest

from error_breakdown import breakdown


def test_bias_and_mae_per_group():
    target = np.array([1.0, 2.0, 3.0, 10.0, 10.0])
    pred = np.array([2.0, 3.0, 4.0, 7.0, 9.0])
    group = np.array(["a", "a", "a", "b", "b"])
    rows = {r["group"]: r for r in breakdown(target, pred, group)}
    assert rows["a"]["n"] == 3 and rows["a"]["bias"] == pytest.approx(1.0)
    assert rows["b"]["bias"] == pytest.approx(-2.0) and rows["b"]["mae"] == pytest.approx(2.0)
    assert rows["b"]["rmse"] == pytest.approx(np.sqrt((9 + 1) / 2))


def test_numeric_columns_are_cut_into_quantile_bins():
    x = np.arange(100, dtype=float)
    target = np.zeros(100)
    pred = x / 100  # error grows with x
    rows = breakdown(target, pred, x, bins=4)
    assert len(rows) == 4
    assert all(r["n"] == 25 for r in rows)
    assert rows[0]["mae"] < rows[-1]["mae"]


def test_weights_enter_the_group_scores():
    target = np.zeros(3)
    pred = np.array([1.0, 1.0, 4.0])
    w = np.array([1.0, 1.0, 2.0])
    (row,) = breakdown(target, pred, np.array(["a", "a", "a"]), weights=w)
    assert row["mae"] == pytest.approx((1 + 1 + 8) / 4)
    assert row["weight"] == pytest.approx(4.0)


def _files(tmp_path, table_rows):
    import duckdb
    pred = tmp_path / "pred.parquet"
    table = tmp_path / "table.parquet"
    duckdb.sql(f"""copy (select * from (values (0, 'm', 'a', 1.0, 1.5), (0, 'm', 'b', 2.0, 2.0), (0, 'm', 'c', 3.0, 2.0))
                   t(repeat, model, id, target, prediction)) to '{pred}' (format parquet)""")
    vals = ", ".join(f"('{i}', '{g}')" for i, g in table_rows)
    duckdb.sql(f"copy (select * from (values {vals}) t(id, region)) to '{table}' (format parquet)")
    return str(pred), str(table)


def test_every_predicted_id_must_find_its_row(tmp_path):
    from error_breakdown import joined_rows
    pred, table = _files(tmp_path, [("a", "x"), ("b", "y"), ("c", "y")])
    assert len(joined_rows(pred, table, "id", "region", "m")) == 3
    pred, table = _files(tmp_path, [("a", "x"), ("b", "y")])            # c has no row in the table
    with pytest.raises(SystemExit):
        joined_rows(pred, table, "id", "region", "m")


def test_a_table_id_that_repeats_stops(tmp_path):
    from error_breakdown import joined_rows
    pred, table = _files(tmp_path, [("a", "x"), ("b", "y"), ("c", "y"), ("c", "z")])
    with pytest.raises(SystemExit):
        joined_rows(pred, table, "id", "region", "m")


def test_residual_moran_by_hand():
    from error_breakdown import residual_moran
    # Four points on the equator at longitudes 0, 1, 3, 7. Nearest neighbours (k = 1): 1, 0, 1, 3.
    # Residuals 1, 1, -1, -1 (mean 0); lags 1, 1, 1, -1; I = (1 + 1 - 1 + 1) / 4 = 0.5.
    r = residual_moran([0, 1, 3, 7], [0, 0, 0, 0], [1, 1, -1, -1], k=1, permutations=99)
    assert r["I"] == pytest.approx(0.5)
    assert r["EI"] == pytest.approx(-1 / 3)


def test_residual_moran_takes_great_circle_neighbours_at_high_latitude():
    from error_breakdown import residual_moran
    # At 60N, 0.015 degrees east is 835 m and 0.01 degrees north is 1,113 m: the east point is the nearer one.
    lon = [0.0, 0.015, 0.0, 10.0, 10.015, 10.0]
    lat = [60.0, 60.0, 60.01, 60.0, 60.0, 60.01]
    resid = [1.0, 1.0, -1.0, 1.0, 1.0, -1.0]
    r = residual_moran(lon, lat, resid, k=1, permutations=99)
    # Great circle: 0 -> 1, 1 -> 0, 2 -> 0 in each group. With the mean removed, z = 1/3, 1/3, -5/3 ... and
    # sum(z * z[neighbour]) is 0, so I = 0. Taking degrees as distances, 0 -> 2 instead, and I = -0.5.
    assert r["I"] == pytest.approx(0.0)

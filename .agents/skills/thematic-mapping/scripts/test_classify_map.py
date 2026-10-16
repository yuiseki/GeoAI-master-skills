"""uvx --with numpy --with duckdb --with shapely --with matplotlib --with pillow --with pytest pytest test_classify_map.py"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from classify_map import assign, breaks, changed_share, check_palette, fisher_jenks

X = np.array([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])


def test_equal_interval_splits_the_range():
    assert breaks(X, "equal", 3) == pytest.approx([1, 4, 7, 10])


def test_quantile_classes_hold_equal_counts():
    b = breaks(X, "quantile", 5)
    counts = np.bincount(assign(X, b), minlength=5)
    assert counts.tolist() == [2, 2, 2, 2, 2]


def test_fisher_jenks_finds_obvious_groups_and_minimises_within_class_squares():
    x = np.array([1.0, 1.1, 1.2, 5.0, 5.2, 9.0, 9.1, 9.3])
    b = fisher_jenks(x, 3)
    assert assign(x, b).tolist() == [0, 0, 0, 1, 1, 2, 2, 2]
    rng = np.random.default_rng(0)
    y = np.sort(rng.lognormal(size=40))
    best = fisher_jenks(y, 3)

    def ssw(cuts):
        c = assign(y, cuts)
        return sum(((y[c == k] - y[c == k].mean()) ** 2).sum() for k in range(3))

    for i in range(1, 39):  # every other 3-class split of the sorted values is no better
        for j in range(i + 1, 40):
            assert ssw(best) <= ssw([y[0], y[i - 1], y[j - 1], y[-1]]) + 1e-9


def test_fixed_thresholds_keep_the_values_given():
    b = breaks(X, "fixed", thresholds=[2.5, 7.5])
    assert b == pytest.approx([1, 2.5, 7.5, 10])
    assert assign(X, b).tolist() == [0, 0, 1, 1, 1, 1, 1, 2, 2, 2]


def test_values_beyond_fixed_thresholds_stop():
    with pytest.raises(SystemExit):
        breaks(X, "fixed", thresholds=[12.0])


def test_on_skewed_values_the_methods_disagree():
    rng = np.random.default_rng(1)
    x = rng.lognormal(0, 1.2, 500)
    eq, qu = assign(x, breaks(x, "equal", 5)), assign(x, breaks(x, "quantile", 5))
    assert (eq == 0).mean() > 0.8  # most units fall in the lowest equal-interval class
    assert changed_share(eq, qu) > 0.5


def test_palette_must_fit_the_kind_of_value():
    check_palette("rate", "viridis")
    check_palette("residual", "RdBu_r")
    check_palette("category", "tab10")
    for name in ("jet", "rainbow", "turbo"):  # rejected for why, not only for not being on the list
        with pytest.raises(SystemExit, match="lightness"):
            check_palette("rate", name)
    for kind, name in (("rate", "jet"), ("rate", "rainbow"), ("residual", "viridis"), ("category", "viridis"),
                       ("rate", "RdBu_r")):
        with pytest.raises(SystemExit):
            check_palette(kind, name)


def _write(tmp_path, values, areas_grow=True):
    import duckdb
    import shapely

    rows = []
    for i, v in enumerate(values):
        g = shapely.box(i * 10, 0, i * 10 + (1 + i if areas_grow else 1), 1 + (i if areas_grow else 0))
        rows.append((str(i), None if v is None else float(v), g.wkt))
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    con.sql("create table t (id varchar, v double, wkt varchar)")
    con.executemany("insert into t values (?, ?, ?)", rows)
    con.sql(f"copy (select id, v, ST_GeomFromText(wkt) as geometry from t) to '{tmp_path}/u.parquet' (format parquet)")
    return str(tmp_path / "u.parquet")


def _cli(tmp_path, *args):
    return subprocess.run([sys.executable, str(Path(__file__).with_name("classify_map.py")), *args],
                          capture_output=True, text=True)


def test_cli_warns_when_counts_follow_area_and_keeps_nodata_apart(tmp_path):
    vals = [i * 10 for i in range(9)] + [None]  # counts that grow with the unit's area, and one NoData
    p = _write(tmp_path, vals)
    out = _cli(tmp_path, p, "id", "v", "--kind", "count", "--unit", "people", "--method", "quantile", "--classes", "3",
               "--crs", "EPSG:6677", "--source", "synthetic v1 2026-10-16", "--png", str(tmp_path / "m.png"))
    assert out.returncode == 0, out.stderr
    assert "correlation with area" in out.stdout and "map a rate or density" in out.stdout
    assert "NoData 1" in out.stdout
    meta = json.loads((tmp_path / "m.json").read_text())
    assert meta["unit"] == "people" and meta["crs"] == "EPSG:6677" and meta["method"] == "quantile"
    assert meta["nodata_units"] == 1 and len(meta["breaks"]) == 4
    from PIL import Image

    assert "quantile" in Image.open(tmp_path / "m.png").info.get("Description", "")


def test_cli_compares_methods_and_common_against_separate_bins(tmp_path):
    rng = np.random.default_rng(2)
    p = _write(tmp_path, list(rng.lognormal(0, 1, 30)), areas_grow=False)
    out = _cli(tmp_path, p, "id", "v", "--kind", "rate", "--unit", "per 1,000", "--method", "equal", "--classes",
               "4", "--compare", "quantile", "jenks", "--crs", "EPSG:6677", "--source", "synthetic")
    assert out.returncode == 0, out.stderr
    assert "units changing class, equal vs quantile" in out.stdout
    assert "units changing class, equal vs jenks" in out.stdout


def test_cli_refuses_a_category_with_numeric_classes(tmp_path):
    p = _write(tmp_path, [1, 2, 3, 1], areas_grow=False)
    out = _cli(tmp_path, p, "id", "v", "--kind", "category", "--method", "quantile", "--classes", "3",
               "--crs", "EPSG:6677", "--source", "s", "--unit", "class")
    assert out.returncode != 0 and "category" in out.stderr

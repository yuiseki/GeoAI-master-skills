"""uvx --with numpy --with duckdb --with shapely --with matplotlib --with pillow --with pytest pytest test_classify_map.py"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from classify_map import (
    EDGE,
    assign,
    breaks,
    changed_share,
    check_palette,
    drop_degenerate_holes,
    fisher_jenks,
    fmt_break,
    label_point,
    rank_anchor,
)

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


def test_zero_area_holes_are_dropped_and_real_holes_kept():
    # jp-admin's 23 wards carry 2,492 interior rings of zero area (seams of the small areas they were built from);
    # drawn with an edge they show as streaks inside the ward
    import shapely

    shell = [(0, 0), (10, 0), (10, 10), (0, 10)]
    seam = [(2, 2), (5, 2), (8, 2), (5, 2)]   # a ring that encloses nothing
    real = [(6, 6), (8, 6), (8, 8), (6, 8)]
    poly, n = drop_degenerate_holes(shapely.Polygon(shell, [seam, real]))
    assert n == 1 and len(poly.interiors) == 1 and poly.area == pytest.approx(96)


def test_legend_numbers_are_written_out_not_in_e_notation():
    assert fmt_break(13028.695264) == "13,029" and fmt_break(5867.82) == "5,868"
    assert fmt_break(16.4) == "16.4" and fmt_break(0.000123) == "0.000123" and fmt_break(-2.5) == "-2.5"


def test_label_point_lies_inside_the_biggest_part():
    import shapely

    u = shapely.Polygon([(0, 0), (10, 0), (10, 10), (8, 10), (8, 2), (2, 2), (2, 10), (0, 10)])  # centroid outside
    islet = shapely.box(100, 100, 101, 101)
    pt = label_point(shapely.MultiPolygon([u, islet]))
    assert u.contains(pt) and not u.centroid.within(u)


def test_boundaries_stand_out_from_every_class_colour():
    # white edges vanish on the lightest class, and neighbours of one class merge into one patch
    import matplotlib
    from matplotlib.colors import to_rgb

    def lum(c):
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    for palette in ("YlOrRd", "viridis", "Blues"):
        cmap = matplotlib.colormaps[palette]
        lightest = max(lum(cmap(x)) for x in np.linspace(0, 1, 9))
        assert lightest - lum(to_rgb(EDGE)) > 0.5


def test_rank_anchor_sits_inside_a_bent_unit_not_on_its_box_corner():
    import shapely

    # An L-shaped municipality: the top-right corner of its box lies in the neighbour that fills the notch.
    unit = shapely.Polygon([(0, 0), (10, 0), (10, 3), (3, 3), (3, 10), (0, 10)])
    neighbour = shapely.box(3, 3, 10, 10)
    pt = rank_anchor(unit)
    assert unit.contains(pt) and not neighbour.contains(pt)


def _write(tmp_path, values, areas_grow=True, names=None):
    import duckdb
    import shapely

    rows = []
    for i, v in enumerate(values):
        g = shapely.box(i * 10, 0, i * 10 + (1 + i if areas_grow else 1), 1 + (i if areas_grow else 0))
        rows.append((str(i), None if v is None else float(v), g.wkt, names[i] if names else f"u{i}"))
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    con.sql("create table t (id varchar, v double, wkt varchar, name varchar)")
    con.executemany("insert into t values (?, ?, ?, ?)", rows)
    con.sql(f"copy (select id, v, name, ST_GeomFromText(wkt) as geometry from t) to '{tmp_path}/u.parquet' "
            "(format parquet)")
    return str(tmp_path / "u.parquet")


def _cli(tmp_path, *args):
    return subprocess.run([sys.executable, str(Path(__file__).with_name("classify_map.py")), *args],
                          check=False, capture_output=True, text=True)


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


def test_cli_stops_when_the_font_cannot_draw_the_japanese_labels(tmp_path):
    # without a Japanese font matplotlib only warns and saves empty boxes; the map must not be written
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    out = _cli(tmp_path, p, "id", "v", "--kind", "rate", "--unit", "人/km²", "--method", "equal", "--classes", "2",
               "--crs", "EPSG:6677", "--source", "国勢調査 2020", "--png", str(tmp_path / "m.png"),
               "--font", "DejaVu Sans")
    assert out.returncode != 0 and "人" in out.stderr
    assert not (tmp_path / "m.png").exists()


def test_cli_ascii_labels_keep_the_default_font(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    out = _cli(tmp_path, p, "id", "v", "--kind", "rate", "--unit", "per km2", "--method", "equal", "--classes", "2",
               "--crs", "EPSG:6677", "--source", "synthetic", "--png", str(tmp_path / "m.png"))
    assert out.returncode == 0, out.stderr
    assert json.loads((tmp_path / "m.json").read_text())["font"] is None


@pytest.mark.skipif(__import__("cjk_font").pick_font(__import__("cjk_font").installed()) is None,
                    reason="no Japanese font on this machine")
def test_cli_draws_japanese_labels_with_a_japanese_font_and_records_it(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    out = _cli(tmp_path, p, "id", "v", "--kind", "rate", "--unit", "人/km²", "--method", "equal", "--classes", "2",
               "--crs", "EPSG:6677", "--source", "国勢調査 2020", "--png", str(tmp_path / "m.png"))
    assert out.returncode == 0, out.stderr
    assert "missing from font" not in out.stderr
    assert json.loads((tmp_path / "m.json").read_text())["font"]


def test_cli_labels_units_with_the_named_column_and_records_it(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False, names=["alpha", "beta", "gamma", "delta"])
    out = _cli(tmp_path, p, "id", "v", "--kind", "rate", "--unit", "per km2", "--method", "equal", "--classes", "2",
               "--crs", "EPSG:6677", "--source", "synthetic", "--label", "name", "--png", str(tmp_path / "m.png"))
    assert out.returncode == 0, out.stderr
    meta = json.loads((tmp_path / "m.json").read_text())
    assert meta["labels"] == "name" and meta["labelled_units"] == 4 and meta["boundary"] == EDGE


def test_cli_labels_few_units_by_id_unless_told_not_to(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    args = ["id", "v", "--kind", "rate", "--unit", "per km2", "--method", "equal", "--classes", "2",
            "--crs", "EPSG:6677", "--source", "synthetic", "--png", str(tmp_path / "m.png")]
    out = _cli(tmp_path, p, *args)
    assert out.returncode == 0, out.stderr
    assert json.loads((tmp_path / "m.json").read_text())["labels"] == "id" and "--label" in out.stdout
    out = _cli(tmp_path, p, *args, "--no-labels")
    assert out.returncode == 0, out.stderr
    assert json.loads((tmp_path / "m.json").read_text())["labels"] is None


def test_cli_checks_the_font_against_the_labels_too(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False, names=["千代田区", "b", "c", "d"])
    out = _cli(tmp_path, p, "id", "v", "--kind", "rate", "--unit", "per km2", "--method", "equal", "--classes", "2",
               "--crs", "EPSG:6677", "--source", "synthetic", "--label", "name", "--png", str(tmp_path / "m.png"),
               "--font", "DejaVu Sans")
    assert out.returncode != 0 and "千" in out.stderr
    assert not (tmp_path / "m.png").exists()


def _context(tmp_path):
    import duckdb

    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    con.sql(f"copy (select * from (values ('West', ST_GeomFromText('POLYGON((-5 -5, 45 -5, 45 20, -5 20, -5 -5))')), "
            f"('East', ST_GeomFromText('POLYGON((45 -5, 100 -5, 100 20, 45 20, 45 -5))'))) t(name, geometry)) "
            f"to '{tmp_path}/ctx.parquet' (format parquet)")
    return str(tmp_path / "ctx.parquet")


BASE = ["id", "v", "--kind", "rate", "--unit", "per km2", "--method", "equal", "--classes", "2",
        "--source", "synthetic v1", "--no-labels"]


def test_cli_stretches_a_longitude_latitude_map_by_latitude(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    out = _cli(tmp_path, p, *BASE, "--crs", "EPSG:4326", "--png", str(tmp_path / "m.png"))
    assert out.returncode == 0, out.stderr
    meta = json.loads((tmp_path / "m.json").read_text())
    assert meta["aspect"] == pytest.approx(1 / np.cos(np.radians(0.5)))
    assert meta["legend"] == "outside" and meta["text_overlaps"] == []


def test_cli_draws_a_background_layer_and_stops_on_a_crs_mismatch(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4, 5, 6], areas_grow=False)  # units reach x = 51, into East
    ctx = _context(tmp_path)
    args = [p, *BASE, "--crs", "EPSG:6677", "--png", str(tmp_path / "m.png"), "--context", ctx,
            "--context-name", "name"]
    out = _cli(tmp_path, *args, "--context-crs", "EPSG:6668", "--context-source", "areas v2")
    assert out.returncode != 0 and "EPSG:6668" in out.stderr and not (tmp_path / "m.png").exists()
    out = _cli(tmp_path, *args, "--context-crs", "EPSG:6677", "--context-source", "areas v2 (abc1234)")
    assert out.returncode == 0, out.stderr
    meta = json.loads((tmp_path / "m.json").read_text())
    assert meta["context"]["source"] == "areas v2 (abc1234)" and meta["context"]["areas"] == 2
    assert sorted(meta["context"]["labelled"]) == ["East", "West"]


def test_cli_highlights_units_with_ranks_and_names_their_areas(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4, 5, 6], areas_grow=False)
    ctx = _context(tmp_path)
    hl = tmp_path / "hl.csv"
    hl.write_text("id,group,rank\n5,top,1\n1,top,2\n4,other,\n")
    args = [p, *BASE, "--crs", "EPSG:6677", "--png", str(tmp_path / "m.png"), "--context", ctx,
            "--context-name", "name", "--context-crs", "EPSG:6677", "--context-source", "s",
            "--highlight", str(hl), "--inset", "-1", "22", "-1", "3", "--expect-units", "6"]
    out = _cli(tmp_path, *args)
    assert out.returncode == 0, out.stderr
    meta = json.loads((tmp_path / "m.json").read_text())
    assert meta["highlight"]["groups"] == {"top": 2, "other": 1} and meta["inset"] == [-1, 22, -1, 3]
    assert meta["zoomed_in_inset"] == ["2"]  # rank 2 (unit 1) lies inside the inset, so it is read there
    rows = (tmp_path / "m-highlights.csv").read_text().splitlines()
    assert rows[0] == "id,group,rank,area" and "5,top,1,East" in rows and "1,top,2,West" in rows
    hl.write_text("id,group,rank\n99,top,1\n")
    out = _cli(tmp_path, *args)
    assert out.returncode != 0 and "99" in out.stderr


def test_cli_stops_when_the_units_drawn_are_not_the_units_expected(tmp_path):
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    out = _cli(tmp_path, p, *BASE, "--crs", "EPSG:6677", "--expect-units", "5", "--png", str(tmp_path / "m.png"))
    assert out.returncode != 0 and "expected 5" in out.stderr and not (tmp_path / "m.png").exists()


def test_reversed_palettes_keep_their_kind():
    check_palette("change", "BrBG_r")
    check_palette("rate", "viridis_r")
    with pytest.raises(SystemExit):
        check_palette("rate", "BrBG_r")
    with pytest.raises(SystemExit):
        check_palette("rate", "jet_r")


def test_cli_drops_unit_outlines_when_units_are_too_small_to_see_between_them(tmp_path):
    import duckdb

    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    con.sql(f"copy (select (i * 100 + j)::varchar as id, (i + j)::double as v, ST_MakeEnvelope(j, i, j + 1, i + 1) "
            f"as geometry from range(100) a(i), range(100) b(j)) to '{tmp_path}/g.parquet' (format parquet)")
    out = _cli(tmp_path, str(tmp_path / "g.parquet"), *BASE, "--crs", "EPSG:6677", "--png", str(tmp_path / "g.png"))
    assert out.returncode == 0, out.stderr
    assert json.loads((tmp_path / "g.json").read_text())["unit_edges"] is False
    p = _write(tmp_path, [1.0, 2, 3, 4], areas_grow=False)
    out = _cli(tmp_path, p, *BASE, "--crs", "EPSG:6677", "--png", str(tmp_path / "m.png"))
    assert json.loads((tmp_path / "m.json").read_text())["unit_edges"] is True

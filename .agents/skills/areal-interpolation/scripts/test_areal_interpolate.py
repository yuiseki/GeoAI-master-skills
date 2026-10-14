"""uvx --from 'duckdb>=1.5.5' --with shapely --with pyproj --with pyarrow --with pytest pytest test_areal_interpolate.py

The zones are rectangles in metres (UTM 54N), so every expected value below is worked out by hand:

    sources   A = [0,100] x [0,100], value 100      B = [100,200] x [0,100], value 200
    targets   X = [0,50]   Y = [50,150]   Z = [150,200]   (all [0,100] in y)

A puts half of its area in X and half in Y; B half in Y and half in Z. So X = 50, Y = 50 + 100, Z = 100.
"""

import duckdb
import numpy as np
import pyproj
import pytest
import shapely

from areal_interpolate import interpolate

X0, Y0 = 500000.0, 3950000.0
UTM = "EPSG:32654"


def box(x1, x2, y1=0, y2=100):
    return shapely.box(X0 + x1, Y0 + y1, X0 + x2, Y0 + y2)


A, B = box(0, 100), box(100, 200)
X, Y, Z = box(0, 50), box(50, 150), box(150, 200)


def write(path, rows, crs=UTM):
    """rows: list of (id, geometry, {column: value}); geometry given in UTM, written in `crs` as WKT."""
    to = pyproj.Transformer.from_crs(UTM, crs, always_xy=True)
    cols = sorted({k for _, _, d in rows for k in d})
    vals = []
    for i, g, d in rows:
        g = shapely.transform(g, lambda c: np.column_stack(to.transform(c[:, 0], c[:, 1]))) if crs != UTM else g
        vals.append(f"('{i}', '{g.wkt}'" + "".join(f", {d.get(c, 'NULL')}" for c in cols) + ")")
    names = ", ".join(["id", "wkt"] + cols)
    duckdb.sql(f"copy (select * from (values {', '.join(vals)}) t({names})) to '{path}' (format parquet)")
    return str(path)


def rows(path, key="target_id"):
    con = duckdb.connect()
    cols = [c[0] for c in con.sql(f"describe select * from '{path}'").fetchall()]
    return {r[cols.index(key)]: dict(zip(cols, r)) for r in con.sql(f"select * from '{path}'").fetchall()}


def run(tmp_path, sources, targets, crs=UTM, **kw):
    s = write(tmp_path / "s.parquet", sources, crs)
    t = write(tmp_path / "t.parquet", targets, crs)
    out, alloc = tmp_path / "out.parquet", tmp_path / "alloc.parquet"
    kw.setdefault("value", "v")
    kw.setdefault("area_crs", UTM)  # the hand-worked areas are UTM metres; the equal-area default is tested below
    rep = interpolate(s, "id", t, "id", str(out), source_crs=crs, target_crs=crs, geom="wkt",
                      allocation_out=str(alloc), **kw)
    return rows(out), rep, str(alloc)


SRC = [("A", A, {"v": 100}), ("B", B, {"v": 200})]
TGT = [("X", X, {}), ("Y", Y, {}), ("Z", Z, {})]


def test_area_weighted_allocation_by_share_of_the_source_area(tmp_path):
    r, rep, _ = run(tmp_path, SRC, TGT)
    assert r["X"]["value"] == pytest.approx(50)    # 100 x 0.5. Dividing by the target's area instead gives 100
    assert r["Y"]["value"] == pytest.approx(150)
    assert r["Z"]["value"] == pytest.approx(100)
    assert (r["Y"]["n_sources"], r["X"]["n_sources"]) == (2, 1)
    assert rep["source_total"] == pytest.approx(300) and rep["allocated_total"] == pytest.approx(300)
    assert rep["ok"]


def test_allocation_table_can_be_audited(tmp_path):
    _, _, alloc = run(tmp_path, SRC, TGT)
    a = {(r[0], r[1]): r for r in duckdb.sql(f"select source_id, target_id, intersection_km2, source_km2, weight, allocated from '{alloc}'").fetchall()}
    assert set(a) == {("A", "X"), ("A", "Y"), ("B", "Y"), ("B", "Z")}
    assert a[("A", "Y")][2] == pytest.approx(0.005, rel=1e-6) and a[("A", "Y")][3] == pytest.approx(0.01, rel=1e-6)
    assert a[("A", "Y")][4] == pytest.approx(0.5) and a[("A", "Y")][5] == pytest.approx(50)


def test_source_area_outside_the_targets_is_not_handed_to_them(tmp_path):
    r, rep, _ = run(tmp_path, SRC, [("X", X, {}), ("Y", Y, {})])
    assert r["Y"]["value"] == pytest.approx(150)   # B still gives Y only half of 200; the other half has no target
    assert rep["allocated_total"] == pytest.approx(200)
    assert rep["uncovered_amount"] == pytest.approx(100)
    assert rep["uncovered_sources"] == 1
    assert not rep["ok"]                           # the total is not conserved, and that is not silent


def test_uncovered_part_can_be_allowed_but_is_still_counted(tmp_path):
    _, rep, _ = run(tmp_path, SRC, [("X", X, {}), ("Y", Y, {})], allow_uncovered=True)
    assert rep["ok"] and rep["uncovered_amount"] == pytest.approx(100)


def test_every_source_and_target_is_accounted_for(tmp_path):
    away = ("W", box(300, 400), {})
    r, rep, _ = run(tmp_path, SRC + [("C", box(500, 600), {"v": 7})], TGT + [away], allow_uncovered=True)
    assert set(r) == {"X", "Y", "Z", "W"}
    assert r["W"]["status"] == "no_source" and r["W"]["value"] is None   # no data, which is not 0
    assert rep["source_rows"] == 3 and rep["target_rows"] == 4
    assert rep["uncovered_sources"] == 1 and rep["uncovered_amount"] == pytest.approx(7)


def test_overlapping_sources_are_reported_not_double_counted_silently(tmp_path):
    c = ("C", box(50, 150), {"v": 60})   # lies over half of A and half of B
    _, rep, _ = run(tmp_path, SRC + [c], TGT)
    assert rep["source_overlap_km2"] == pytest.approx(0.01, rel=1e-6)
    assert not rep["ok"]


def test_overlapping_targets_hand_out_the_same_value_twice_and_are_reported(tmp_path):
    _, rep, _ = run(tmp_path, SRC, TGT + [("XY", box(0, 100), {})])
    assert rep["target_overlap_km2"] == pytest.approx(0.01, rel=1e-6)
    assert rep["allocated_total"] == pytest.approx(400)   # A is handed out twice
    assert not rep["ok"]


def test_slivers_are_counted(tmp_path):
    xs = ("X", box(0, 100.001), {})   # reaches 1 mm into B
    _, rep, _ = run(tmp_path, SRC, [xs, ("Y", box(100.001, 150), {}), ("Z", Z, {})])
    assert rep["sliver_pairs"] == 1


def test_area_is_measured_on_an_equal_area_crs_not_in_degrees(tmp_path):
    # One source from the equator to 60N, split at 30N. On the sphere the southern half holds
    # sin 30 / sin 60 = 57.7 % of the area; degrees give 50 %, Web Mercator 41.7 %.
    s = [("S", shapely.box(140, 0, 141, 60), {"v": 1000})]
    t = [("south", shapely.box(140, 0, 141, 30), {}), ("north", shapely.box(140, 30, 141, 60), {})]
    sp, tp = tmp_path / "s.parquet", tmp_path / "t.parquet"
    for path, rs in ((sp, s), (tp, t)):
        vals = ", ".join(f"('{i}', '{g.wkt}', {d.get('v', 'NULL')})" for i, g, d in rs)
        duckdb.sql(f"copy (select * from (values {vals}) t(id, wkt, v)) to '{path}' (format parquet)")
    out = tmp_path / "o.parquet"
    interpolate(str(sp), "id", str(tp), "id", str(out), value="v", source_crs="EPSG:4326", target_crs="EPSG:4326", geom="wkt")
    assert rows(out)["south"]["value"] == pytest.approx(577, abs=5)


def test_units_in_different_crs_are_brought_together(tmp_path):
    s = write(tmp_path / "s.parquet", SRC, "EPSG:4326")
    t = write(tmp_path / "t.parquet", TGT, UTM)
    out = tmp_path / "o.parquet"
    interpolate(s, "id", t, "id", str(out), value="v", source_crs="EPSG:4326", target_crs=UTM, geom="wkt", area_crs=UTM)
    assert rows(out)["Y"]["value"] == pytest.approx(150, rel=1e-4)


def test_a_ratio_is_rebuilt_from_its_numerator_and_denominator(tmp_path):
    # A: 50 of 100 people employed (0.5). B: 40 of 200 (0.2). Y gets 25 + 20 of 50 + 100 = 0.3.
    src = [("A", A, {"num": 50, "den": 100}), ("B", B, {"num": 40, "den": 200})]
    r, rep, _ = run(tmp_path, src, TGT, value=None, kind="ratio", numerator="num", denominator="den")
    assert r["Y"]["value"] == pytest.approx(0.3)   # 0.35 if the rates were spread by area
    assert r["Y"]["numerator"] == pytest.approx(45) and r["Y"]["denominator"] == pytest.approx(150)
    assert rep["ok"]


def test_an_intensive_value_is_averaged_not_handed_out(tmp_path):
    src = [("A", A, {"v": 0.5}), ("B", B, {"v": 0.2})]
    r, _, _ = run(tmp_path, src, TGT, kind="intensive")
    assert r["X"]["value"] == pytest.approx(0.5)   # 0.25 if the rate were split like a count
    assert r["Y"]["value"] == pytest.approx(0.35)


def test_auxiliary_weights_move_the_value_to_where_the_weight_is(tmp_path):
    # Inside A: weight 1 on [0,40] (in X) and weight 3 on [60,100] (in Y), so A gives X 25 and Y 75.
    # B holds no weight and falls back to its area: 100 to Y, 100 to Z.
    aux = write(tmp_path / "aux.parquet", [("a1", box(0, 40), {"w": 1}), ("a2", box(60, 100), {"w": 3})])
    r, rep, _ = run(tmp_path, SRC, TGT, method="auxiliary", aux=aux, aux_weight="w", aux_crs=UTM)
    assert r["X"]["value"] == pytest.approx(25)
    assert r["Y"]["value"] == pytest.approx(175)
    assert r["Z"]["value"] == pytest.approx(100)
    assert rep["fallback_sources"] == 1 and rep["ok"]


def test_invalid_geometry_is_repaired_and_counted(tmp_path):
    bow = shapely.Polygon([(X0, Y0), (X0 + 100, Y0 + 100), (X0 + 100, Y0), (X0, Y0 + 100), (X0, Y0)])
    _, rep, _ = run(tmp_path, [("A", bow, {"v": 100})], TGT, allow_uncovered=True)
    assert rep["invalid_sources"] == 1
    assert rep["invalid_sources_after_projection"] == 0


def test_duplicate_ids_stop(tmp_path):
    with pytest.raises(SystemExit):
        run(tmp_path, SRC + [("A", box(300, 400), {"v": 1})], TGT)


def test_a_source_reaching_past_the_auxiliary_coverage_falls_back_to_its_area(tmp_path):
    # Weight only in B's western half [100,150] (in Y). The layer was only collected over [0,150]:
    # B's eastern half has no weight because nobody looked, not because nothing is there.
    aux = write(tmp_path / "aux.parquet", [("a3", box(100, 150), {"w": 1})])
    cov = write(tmp_path / "cov.parquet", [("c", box(0, 150), {})])
    r, _, _ = run(tmp_path, SRC, TGT, method="auxiliary", aux=aux, aux_weight="w", aux_crs=UTM)
    assert r["Y"]["value"] == pytest.approx(50 + 200)    # without the coverage, all of B goes where the weight is
    r, rep, _ = run(tmp_path, SRC, TGT, method="auxiliary", aux=aux, aux_weight="w", aux_crs=UTM, aux_coverage=cov)
    assert r["Y"]["value"] == pytest.approx(50 + 100) and r["Z"]["value"] == pytest.approx(100)
    assert rep["fallback_sources"] == 2                  # A holds no weight; B reaches past the coverage


def test_a_hairline_overlap_between_targets_is_reported_but_does_not_stop(tmp_path):
    tg = [("X", box(0, 50.00001), {}), ("Y", Y, {}), ("Z", Z, {})]   # 0.001 m2 of 20,000 m2
    _, rep, _ = run(tmp_path, SRC, tg)
    assert 0 < rep["target_overlap_km2"] < 1e-8
    assert rep["ok"]

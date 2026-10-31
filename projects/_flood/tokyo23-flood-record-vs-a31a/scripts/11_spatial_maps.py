"""Figures 1-3 with analysis-visualize's spatial_result_map.py: the cells, the wards, the main rivers and their names.

uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pyproj --with matplotlib python scripts/11_spatial_maps.py

Reads artifacts/_flood/tokyo23-flood-record-vs-a31a/maps/{cells.csv, wards_6677.parquet} (07_maps.py) and the OSM
waterways, writes the GeoJSON inputs and configs next to them, and draws outputs/fig{1,2,3}_*.png with a JSON
beside each (counts, breaks, the texts placed and their overlaps). Everything is in EPSG:6677 metres.
"""
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import shapely
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a"
M = ART / "maps"
OUT = HERE.parent / "outputs"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/spatial_result_map.py"
RIVERS = ["荒川", "隅田川", "江戸川", "中川", "多摩川", "神田川", "石神井川", "目黒川", "呑川", "妙正寺川", "善福寺川", "綾瀬川"]
SIZE = 100.0
SOURCE = ("tokyo-flood-record-jp@354b0d9, ksj-a31a-flood-tokyo23@5b22592, GSI DEM5A (2026-10-26), OSM 2026-08 (38f7a5f), "
          "WorldCover 2021; 区界 jp-admin-2026-09@e6c87b1")
BASE = {"crs": "EPSG:6677", "source": SOURCE, "data_version": "学習 1974-1996、試験 1997-2019",
        "geometry_source": "100 m 格子 (scripts/02_grid.py)、区界 jp-admin-2026-09", "roads_label": "主な川 (OSM、暗渠を除く)",
        "method": "HistGradientBoosting の種 5 つの平均 (scripts/03_static.py)"}


def square(x, y):
    h = SIZE / 2
    return {"type": "Polygon", "coordinates": [[[x - h, y - h], [x + h, y - h], [x + h, y + h], [x - h, y + h], [x - h, y - h]]]}


def write_cells(rows, keys, path):
    feats = [{"type": "Feature", "properties": {"id": r["cell"], **{k: r[k] for k in keys}}, "geometry": square(r["x"], r["y"])}
             for r in rows]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return len(feats)


def main():
    c = duckdb.connect()
    c.execute("load spatial")
    cells = c.execute(f"select cell, x, y, model_pct, agree, test_cat from read_csv('{M / 'cells.csv'}') order by cell").fetchall()
    rows = [dict(zip(["cell", "x", "y", "model_pct", "agree", "test_cat"], r)) for r in cells]
    wards = [{"name": n, "geometry": json.loads(g)} for n, g in
             c.execute(f"select name, st_asgeojson(geometry) from '{M / 'wards_6677.parquet'}' order by name").fetchall()]

    # rivers: OSM is EPSG:3857; open (not tunnelled) river lines of the named rivers, clipped to the wards plus 1 km
    t = Transformer.from_crs("EPSG:3857", "EPSG:6677", always_xy=True)
    area = shapely.union_all([shapely.geometry.shape(w["geometry"]) for w in wards]).buffer(1000)
    roads, landmarks = [], []
    for name in RIVERS:
        lines = [shapely.from_wkb(bytes(w)) for (w,) in c.execute(
            f"""select st_aswkb(way) from '{ART / 'raw/osm_waterway.parquet'}'
                where waterway = 'river' and name = ? and (tunnel is null or tunnel = 'no')""", [name]).fetchall()]
        lines = [shapely.transform(g, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1]))) for g in lines]
        g = shapely.intersection(shapely.union_all(lines), area) if lines else None
        if g is None or g.is_empty:
            print("no open line for", name); continue
        roads.append({"tier": "major", "geometry": shapely.geometry.mapping(g)})
        parts = list(getattr(g, "geoms", [g]))
        longest = max(parts, key=lambda p: p.length)
        p = longest.interpolate(0.5, normalized=True)
        landmarks.append({"name": name, "coordinates": [p.x, p.y]})
    outline = shapely.geometry.mapping(shapely.union_all([shapely.geometry.shape(w["geometry"]) for w in wards]))
    context = {"context_areas": wards, "outline": outline, "roads": roads, "landmarks": landmarks, "landmark_fontsize": 8}

    figs = [
        ("fig1_model_rank", rows, ["model_pct"], BASE | context | {
            "question": "予測モデルの予測得点の順位 (1974〜1996 年の記録で学習)", "value": "model_pct", "kind": "sequential",
            "unit": "セル", "value_unit": "%", "class_method": "fixed", "classes": 6, "thresholds": [1, 5, 10, 20, 46.66],
            "palette": "YlOrRd_r", "unit_linewidth": 0, "expect_units": len(rows)}),
        ("fig2_agreement", rows, ["agree"], BASE | context | {
            "question": "予測モデルの上位 46.7% と A31a 想定最大規模の区域", "value": "agree", "kind": "category",
            "unit": "セル", "categories": {"1": "両方", "2": "予測モデルだけ", "3": "A31a だけ", "4": "どちらでもない"},
            "category_colors": {"1": "#2b6cb0", "2": "#d62728", "3": "#e377c2", "4": "#e8e8e8"}, "unit_linewidth": 0, "expect_units": len(rows)}),
        ("fig3_test_cells", [r for r in rows if r["test_cat"] is not None], ["test_cat"], BASE | context | {
            "question": "1997〜2019 年に浸水が記録されたセルは、どちらの区域に入ったか", "value": "test_cat", "kind": "category",
            "unit": "セル", "categories": {"1": "両方", "2": "予測モデルだけ", "3": "A31a だけ", "4": "どちらでもない"},
            "category_colors": {"1": "#2b6cb0", "2": "#d62728", "3": "#e377c2", "4": "#222222"}, "unit_linewidth": 0.15, "expect_units": 3057}),
    ]
    for name, rs, keys, cfg in figs:
        gj, cj = M / f"{name}.geojson", M / f"{name}.config.json"
        write_cells(rs, keys, gj)
        cj.write_text(json.dumps(cfg, ensure_ascii=False))
        subprocess.run([sys.executable, str(DRAW), str(gj), str(cj), str(OUT / f"{name}.png")], check=True)
        meta = json.loads((OUT / f"{name}.json").read_text())
        print(name, meta["counts"], "landmarks", meta["labelled_landmarks"], "overlaps", len(meta["text_overlaps"]))


if __name__ == "__main__":
    main()

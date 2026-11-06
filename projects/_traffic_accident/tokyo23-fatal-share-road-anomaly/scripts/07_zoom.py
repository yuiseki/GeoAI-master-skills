"""B8 (exploratory): close-up of the 1 km mesh 53393553 (目黒区), the one 1 km mesh with q < 0.05.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pandas --with pyarrow --with shapely --with pyproj \
  --with matplotlib python -u scripts/07_zoom.py

Edges: the road links of 06_links.py inside the mesh (plus 60 m), coloured and widened by their accidents of
2019-2025. Points: the 8 fatal accidents, split by whether a pedestrian or cyclist was a party, and the centres
of the four 500 m meshes. Writes outputs/zoom_meguro.png (+ .json) and outputs/zoom_meguro_fatal.csv.
"""
import importlib
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
an = importlib.import_module("02_anomaly")
ex = importlib.import_module("03_explore")

MESH = "53393553"
PAD = 60.0
NETWORK_MAP = HERE.parents[3] / ".agents/skills/analysis-visualize/scripts/network_map.py"


def main():
    tf = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
    lo0, la0, lo1, la1 = ex.mesh_bounds(MESH)
    xs, ys = tf.transform([lo0, lo1, lo0, lo1], [la0, la0, la1, la1])
    x0, x1, y0, y1 = min(xs) - PAD, max(xs) + PAD, min(ys) - PAD, max(ys) + PAD
    c = duckdb.connect()
    c.execute("load spatial")
    out_edges = an.ART / f"zoom_{MESH}_links.parquet"
    c.execute(f"""copy (select n, O, name, (O > 0) has_fatal, case when O > 0 then name end label, geometry
        from '{an.ART / 'links.parquet'}'
        where st_intersects(geometry, st_makeenvelope({x0}, {y0}, {x1}, {y1}))) to '{out_edges}' (format parquet)""")
    stats = c.execute(f"select count(*), max(n), sum(n), sum(O) from '{out_edges}'").fetchone()
    print("links in view, max n, accidents, fatal:", stats, flush=True)

    d = an.load()
    f = d[(d.m1000 == MESH) & (d.fatal == 1)].copy()
    f["x"], f["y"] = tf.transform(f.longitude.values, f.latitude.values)
    lk = c.execute(f"select name, n, O, st_aswkb(geometry) wkb from '{out_edges}'").df()
    import shapely
    tree = shapely.STRtree(shapely.from_wkb(lk.wkb.map(bytes)))
    near = tree.nearest(shapely.points(f[["x", "y"]].values))
    f["link_name"], f["link_accidents"], f["link_fatal"] = lk.name.values[near], lk.n.values[near], lk.O.values[near]
    print(f.groupby("link_name").size().to_string(), flush=True)
    f[["link_name", "link_accidents", "link_fatal", "m500", "occ_year", "shape_g", "width_g", "median_g", "vulnerable", "x", "y"]].to_csv(
        an.OUT / "zoom_meguro_fatal.csv", index=False, encoding="utf-8")
    args = []
    for v, label, marker, colour in (("歩行者か自転車", "死亡事故 (歩行者か自転車が当事者)", "o", "#7b2cbf"),
                                      ("その他", "死亡事故 (その他)", "s", "#000000")):
        sel = f[f.vulnerable == v]
        p = an.ART / f"zoom_{MESH}_{'v' if v != 'その他' else 'o'}.csv"
        sel[["x", "y"]].to_csv(p, index=False)
        args += ["--points", f"{p},{label} ({len(sel)}),{marker},{colour}"]
    cen = []
    for q in "1234":
        a, b, cc, dd = ex.mesh_bounds(MESH + q)
        cx, cy = tf.transform((a + cc) / 2, (b + dd) / 2)
        cen.append(dict(x=cx, y=cy))
    p = an.ART / f"zoom_{MESH}_centres.csv"
    pd.DataFrame(cen).to_csv(p, index=False)
    args += ["--points", f"{p},500 m メッシュの中心 (4),P,#9aa0a6"]
    cmd = [sys.executable, str(NETWORK_MAP), str(out_edges), "--crs", "EPSG:6677",
           "--source", "警察庁 交通事故統計オープンデータ 389500a (2019〜2025 年)、OSM 2026-08-31 (ODbL)。加工して作成",
           "--question", "1 km メッシュ 53393553 (目黒区) の死亡事故 8 件は、どの道のどこで起きたか",
           "--value", "n", "--value-label", "リンクの人身事故 (2019〜2025 年)", "--unit", "件",
           "--bins", "1", "3", "10", "30", "--width-range", "0.8", "5", "--base-width", "0.4",
           "--highlight", "has_fatal", "--highlight-label", "死亡事故のあったリンク", "--label-col", "label",
           "--view", str(x0), str(y0), str(x1), str(y1),
           "--title", "目黒区 53393553: 死亡事故 8 件の場所と、道路リンクごとの事故の数",
           "--note", "表示の範囲は 1 km メッシュに 60 m の余白。事故は 30 m 以内の最も近いリンクに数えた",
           "--png", str(an.OUT / "zoom_meguro.png")] + args
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()

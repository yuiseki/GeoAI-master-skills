"""B8 close-ups: how the approaches of one site change with the assumed gate area (site access 0, 30, 50 m).

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas \
  --with matplotlib python -u scripts/13_site_zoom.py

Same graph and access as 11_site_approaches.py. For each named site, with R = 100 m and L = 200 m: the access nodes,
the centres of the approach groups (cutdetour.approaches) and the centres of the 10 m disks that close the site
(cutdetour.single_gate) for each access radius. Drawn over the B7 blockage edges (spot_edges.parquet) with
analysis-visualize/network_map.py. Writes outputs/site_approaches/zoom_<site>.png (+ .json) and zoom_points.csv.
"""
import importlib
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
run = importlib.import_module("02_run")
import cutdetour as cd  # noqa: E402

SITES = {"E1310600023201": "shinobugaoka", "E1310600005201": "higashiasakusa"}  # 忍岡小学校、東浅草小学校
ACCESS = (0.0, 30.0, 50.0)
R, L, MERGE, DISK = 100.0, 200.0, 20.0, 10.0
HALF = 230.0
NETWORK_MAP = HERE.parents[3] / ".agents/skills/analysis-visualize/scripts/network_map.py"
LAYERS = [  # (kind, access, label, marker, colour)
    ("access", 50.0, "入口 50 m の節点", ".", "#9aa0a6"),
    ("access", 30.0, "入口 30 m の節点", ".", "#4d5156"),
    # later layers are drawn on top: the 0 m mark stays visible where the three radii give the same place
    ("gate", 50.0, "進入路 (入口 50 m)", "o", "#1f6fb2"),
    ("gate", 30.0, "進入路 (入口 30 m)", "s", "#2a9d8f"),
    ("gate", 0.0, "進入路 (入口 0 m)", "X", "#7b2cbf"),
    ("disk", 0.0, "1 つで閉じる封鎖の中心 (入口 0 m)", "P", "#000000"),
    ("disk", 30.0, "1 つで閉じる封鎖の中心 (入口 30 m)", "*", "#000000"),
    ("site", 0.0, "避難場所の地点", "^", "#d62728"),
]


def main():
    out = HERE.parent / "outputs" / "site_approaches"
    art = run.ART / "site_approaches"
    art.mkdir(parents=True, exist_ok=True)
    raw = run.ART / "raw_b3000"
    c = duckdb.connect()
    c.execute("load spatial")
    lines = c.execute(f"select * exclude (g), st_aswkb(g) wkb from '{raw}/lines.parquet'").df()
    lines["geom"] = shapely.from_wkb(lines.pop("wkb").map(bytes))
    sites = c.execute(f"select * exclude (g), st_x(g) x, st_y(g) y from '{raw}/sites.parquet'").df()
    walk = lines[[run.walkable(r, False) for r in lines.itertuples()]].reset_index(drop=True)
    g = cd.build_graph(walk.geom.values)
    ground = cd.ground_nodes(g, np.flatnonzero(walk.bridge.map(run.is_set).values), min_component_m=run.GROUND_MIN_M)
    cand = np.flatnonzero(ground & (g.comp == g.main))
    tree = cKDTree(g.xy[cand])

    rows = []
    for cid, key in SITES.items():
        s = sites[sites.common_id == cid].iloc[0]
        p = np.array([s.x, s.y])
        snapped, _ = cd.snap(g, [p], allowed=ground)
        rows.append(dict(site=key, kind="site", access=0.0, x=p[0], y=p[1], name=s["name"]))
        for a in ACCESS:
            S = np.unique(np.r_[snapped, cand[tree.query_ball_point(p, a)]]).astype(int) if a > 0 else snapped
            for x in S:
                rows.append(dict(site=key, kind="access", access=a, x=g.xy[x, 0], y=g.xy[x, 1], name=s["name"]))
            ap = cd.approaches(g, S, R=R, L=L, merge_m=MERGE)
            cut, lab = np.asarray(ap["cut"], int), np.asarray(ap["groups"], int)
            for gi in range(ap["k"]):
                e = cut[lab == gi]
                xy = np.vstack([g.xy[g.u[e]], g.xy[g.v[e]]]).mean(axis=0)
                rows.append(dict(site=key, kind="gate", access=a, x=xy[0], y=xy[1], name=s["name"], k=ap["k"]))
            _, _, spots = cd.single_gate(g, S, R=R, L=L, r=DISK, return_spots=True)
            for xy in spots:
                rows.append(dict(site=key, kind="disk", access=a, x=xy[0], y=xy[1], name=s["name"]))
    pts = pd.DataFrame(rows)
    pts.to_csv(out / "zoom_points.csv", index=False, encoding="utf-8")
    print(pts.groupby(["site", "kind", "access"]).size().to_string())

    edges = run.ART / "spot_r10_a50_o50" / "spot_edges.parquet"
    for key in SITES.values():
        t = pts[pts.site == key]
        name = t.name.iloc[0]
        sx, sy = t[t.kind == "site"][["x", "y"]].values[0]
        k = {a: int(t[(t.kind == "gate") & (t.access == a)].shape[0]) for a in ACCESS}
        args = []
        for kind, a, label, marker, colour in LAYERS:
            sel = t[(t.kind == kind) & (t.access == a)]
            if kind == "access" and a == 50.0:
                sel = sel[~sel[["x", "y"]].apply(tuple, axis=1).isin(
                    set(t[(t.kind == "access") & (t.access == 30.0)][["x", "y"]].apply(tuple, axis=1)))]
            if sel.empty:
                continue
            f = art / f"zoom_{key}_{kind}_{a:g}.csv"
            sel[["x", "y"]].to_csv(f, index=False)
            args += ["--points", f"{f},{label} ({len(sel)}),{marker},{colour}"]
        cmd = [sys.executable, str(NETWORK_MAP), str(edges), "--crs", "EPSG:6677",
               "--source", "OSM 2026-08-31 (ODbL)、国土地理院 指定緊急避難場所 2026-10-06 取得。加工して作成",
               "--question", f"{name}の進入路の数は、門の位置の仮定 (入口の広さ) でどう変わるか",
               "--value", "n_flagged", "--value-label", "そこを塞ぐと 1.5 倍以上か届かない出発点 (B7)", "--unit", "点",
               "--bins", "1", "5", "20", "50", "130", "--width-range", "1", "6", "--base-width", "0.8",
               "--view", str(sx - HALF), str(sy - HALF), str(sx + HALF), str(sy + HALF),
               "--title", f"{name}: 進入路の数は入口 0 m で {k[0.0]}、30 m で {k[30.0]}、50 m で {k[50.0]}",
               "--note", "進入路は入口から 100 m の範囲で数え、20 m 以内の塞ぎ方を 1 か所にまとめた。封鎖の半径 10 m",
               "--png", str(out / f"zoom_{key}.png")] + args
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()

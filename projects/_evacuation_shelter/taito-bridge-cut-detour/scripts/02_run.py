"""Single-structure cut detours from Taito-ku origins to designated flood evacuation sites (EXPERIMENT_PLAN.md).

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas \
  python scripts/02_run.py --variant main

Variants (one setting changed from main): see VARIANTS. Writes
  outputs/<variant>/summary.json        graph, snapping, origins, structures, counts
  outputs/<variant>/cells.csv           500 m half-mesh cells clipped to Taito-ku, sorted by median increment
  outputs/<variant>/structures.csv      structures that lengthen at least one origin's route, with what they cross
  artifacts/.../<variant>/origins.parquet   every origin point: d0, d*, the structure, cell
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

import cutdetour as cd

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_evacuation_shelter/taito-bridge-cut-detour"
TAITO = "13106"

EXCLUDE_HW = {"motorway", "motorway_link", "construction", "proposed", "platform", "corridor", "elevator",
              "raceway", "bus_guideway", "bridleway", "abandoned", "disused", "razed"}
FOOT_OK = {"yes", "designated", "permissive"}
WATERWAY = {"river", "canal", "stream", "drain", "ditch"}
RAILWAY = {"rail", "light_rail", "monorail", "subway", "narrow_gauge", "funicular"}

MAIN = dict(cluster_m=10.0, sites="all", corridor=False, buffer_m=5000, tunnels=False, hazard="flood", cut="single")
VARIANTS = {
    "main": {},
    "cluster5": dict(cluster_m=5.0),
    "cluster20": dict(cluster_m=20.0),
    "sites_taito": dict(sites="taito"),
    "corridor": dict(corridor=True),
    "buffer3000": dict(buffer_m=3000),
    "buffer8000": dict(buffer_m=8000),
    "tunnels": dict(tunnels=True),
    # exploratory: not a single cut
    "all_rail": dict(cut="kind:rail"),     # every bridge that crosses a railway removed at once
    "all_river": dict(cut="kind:river"),   # every bridge that crosses water removed at once
    # exploratory: every walkable way (not only bridges) cut one at a time, without grouping parallel lines
    "allways": dict(cut="allways"),
}

GRID_M = 50.0
SNAP_MAX_M = 100.0
GROUND_MIN_M = 1000.0  # ground components with less road than this are pockets (stairs, yards), not neighbourhoods


def is_set(s):
    return s is not None and s == s and s not in ("no", "")


def walkable(r, corridor):
    hw = r.highway
    if hw is None or hw != hw:
        return False
    if hw in EXCLUDE_HW and not (corridor and hw == "corridor"):
        return False
    if r.foot == "no":
        return False
    if r.access in ("no", "private") and r.foot not in FOOT_OK:
        return False
    return True


def half_mesh(lon, lat):
    """9-digit half (500 m) mesh code: 3rd mesh 8 digits + quadrant 1 SW, 2 SE, 3 NW, 4 NE."""
    p = lat * 1.5
    ab = int(p)
    r = (p - ab) * 8
    e = int(r)
    r2 = (r - e) * 10
    g = int(r2)
    q_lat = int((r2 - g) * 2)
    x = lon - 100
    cdd = int(x)
    s = (x - cdd) * 8
    f = int(s)
    s2 = (s - f) * 10
    h = int(s2)
    q_lon = int((s2 - h) * 2)
    return f"{ab:02d}{cdd:02d}{e}{f}{g}{h}{1 + q_lon + 2 * q_lat}"


def crossing_kinds(geom, river_lines, water_polys, rail_lines, road_lines):
    k = []
    if any(geom.crosses(x) for x in river_lines.query_geoms(geom)) or \
            any(geom.intersects(x) for x in water_polys.query_geoms(geom)):
        k.append("river")
    if any(geom.crosses(x) for x in rail_lines.query_geoms(geom)):
        k.append("rail")
    if any(geom.crosses(x) for x in road_lines.query_geoms(geom)):
        k.append("road")
    return k or ["other"]


class Tree:
    def __init__(self, geoms):
        self.g = list(geoms)
        self.t = shapely.STRtree(self.g) if self.g else None

    def query_geoms(self, geom):
        if self.t is None:
            return []
        return [self.g[i] for i in self.t.query(geom)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="main", choices=sorted(VARIANTS))
    a = ap.parse_args()
    cfg = {**MAIN, **VARIANTS[a.variant]}
    raw = ART / f"raw_b{cfg['buffer_m']}"
    out = PROJ / "outputs" / a.variant
    out.mkdir(parents=True, exist_ok=True)
    (ART / a.variant).mkdir(parents=True, exist_ok=True)

    c = duckdb.connect()
    c.execute("load spatial")
    lines = c.execute(f"select * exclude (g), st_aswkb(g) wkb from '{raw}/lines.parquet'").df()
    lines["geom"] = shapely.from_wkb(lines.pop("wkb").map(bytes))
    water = c.execute(f"select st_aswkb(g) wkb from '{raw}/water.parquet'").df()
    water_geoms = shapely.from_wkb(water.wkb.map(bytes))
    taito = shapely.from_wkb(bytes(c.execute(f"select st_aswkb(g) from '{raw}/taito.parquet'").fetchall()[0][0]))
    sites = c.execute(f"select * exclude (g), st_x(g) x, st_y(g) y from '{raw}/sites.parquet'").df()
    mesh = c.execute(f"select code, pop from '{raw}/mesh1km.parquet'").df()

    # walking graph
    walk = lines[[walkable(r, cfg["corridor"]) for r in lines.itertuples()]].reset_index(drop=True)
    g = cd.build_graph(walk.geom.values)
    main_share = float(np.mean(g.comp == g.main))
    assert main_share >= 0.9, main_share

    # structures
    is_bridge = walk.bridge.map(is_set).values
    struct_mask = is_bridge.copy()
    if cfg["tunnels"]:
        lay = pd.to_numeric(walk.layer, errors="coerce").fillna(0).values
        struct_mask |= walk.tunnel.map(is_set).values | (lay < 0) | (walk.covered == "yes").values
    struct_idx = np.flatnonzero(struct_mask)
    groups = cd.cluster_lines(walk.geom.values, struct_idx, cfg["cluster_m"])

    rivers = Tree(lines.geom[lines.waterway.isin(WATERWAY) & ~lines.tunnel.map(is_set)])
    wpoly = Tree(water_geoms)
    rails = Tree(lines.geom[lines.railway.isin(RAILWAY) & ~lines.tunnel.map(is_set)])
    roads = Tree(lines.geom[lines.highway.notna() & ~lines.bridge.map(is_set) & ~lines.tunnel.map(is_set)])
    kind_note = None
    if cfg["cut"].startswith("kind:"):
        want = cfg["cut"].split(":")[1]
        members = {}
        for li, gid in groups.items():
            members.setdefault(gid, []).append(li)
        chosen = [gid for gid, mem in members.items()
                  if want in crossing_kinds(shapely.union_all(walk.geom.values[mem]), rivers, wpoly, rails, roads)]
        groups = {li: 0 for gid in chosen for li in members[gid]}
        kind_note = dict(kind=want, structures_removed_together=len(chosen), lines=len(groups))
    elif cfg["cut"] == "allways":
        groups = {i: i for i in range(len(walk))}

    # sites
    hz = sites[sites[cfg["hazard"]].fillna(False)]
    if cfg["sites"] == "taito":
        hz = hz[hz.common_id.str[1:6] == TAITO]
    ground = cd.ground_nodes(g, struct_idx, min_component_m=GROUND_MIN_M)
    src, src_d = cd.snap(g, hz[["x", "y"]].values, allowed=ground)

    # origins: 50 m grid inside Taito
    x0, y0, x1, y1 = taito.bounds
    gx, gy = np.meshgrid(np.arange(math.floor(x0 / GRID_M) * GRID_M + GRID_M / 2, x1, GRID_M),
                         np.arange(math.floor(y0 / GRID_M) * GRID_M + GRID_M / 2, y1, GRID_M))
    pts = np.c_[gx.ravel(), gy.ravel()]
    inside = shapely.contains_xy(taito, pts[:, 0], pts[:, 1])
    pts = pts[inside]
    wtree = shapely.STRtree(water_geoms)
    in_water = np.zeros(len(pts), bool)
    hit_pt, _ = wtree.query(shapely.points(pts), predicate="within")
    in_water[hit_pt] = True
    onode, od = cd.snap(g, pts, allowed=ground)
    ok = (od <= SNAP_MAX_M) & ~in_water
    to_ll = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
    lon, lat = to_ll.transform(pts[:, 0], pts[:, 1])
    cells = np.array([half_mesh(lo, la) for lo, la in zip(lon, lat)])

    d0, cuts = cd.cut_distances(g, src, groups, onode[ok])
    dstar, who = cd.worst_cut(d0, cuts)

    o = pd.DataFrame({"x": pts[:, 0], "y": pts[:, 1], "lon": lon, "lat": lat, "cell": cells, "snap_m": od,
                      "in_water": in_water, "used": ok})
    o["d0"] = np.nan
    o["dstar"] = np.nan
    o["struct"] = -1
    o.loc[ok, "d0"] = d0
    o.loc[ok, "dstar"] = dstar
    o.loc[ok, "struct"] = who
    o["inc"] = o.dstar - o.d0
    o["ratio"] = np.where(o.d0 > 0, o.dstar / o.d0.where(o.d0 > 0), np.nan)
    o.to_parquet(ART / a.variant / "origins.parquet")

    # structures that matter
    by_group = {}
    for li, gid in groups.items():
        by_group.setdefault(gid, []).append(li)
    u = o[o.used]
    rows = []
    for gid in sorted(set(u.struct) - {-1}):
        mem = by_group[gid]
        geom = shapely.union_all(walk.geom.values[mem])
        names = Counter(n for n in list(walk.name.values[mem]) + list(walk.bridge_name.values[mem])
                        if isinstance(n, str) and n)
        if cfg["cut"].startswith("kind:"):
            kinds = [cfg["cut"].split(":")[1] + " (all at once)"]
        elif is_bridge[mem].any():
            kinds = crossing_kinds(geom, rivers, wpoly, rails, roads)
        elif cfg["cut"] == "allways":
            kinds = ["way:" + str(walk.highway.values[mem[0]])]
        else:
            kinds = ["tunnel"]
        if cfg["tunnels"] and not is_bridge[mem].all():
            kinds = sorted(set(kinds) | {"tunnel"})
        sel = u[u.struct == gid]
        cen = geom.centroid
        clon, clat = to_ll.transform(cen.x, cen.y)
        rows.append(dict(struct=gid, name=names.most_common(1)[0][0] if names else "", kinds="+".join(kinds),
                         n_lines=len(mem), length_m=round(geom.length, 1), lon=round(clon, 6), lat=round(clat, 6),
                         n_origins_worst=len(sel), n_unreachable=int(np.isinf(sel.dstar).sum()),
                         inc_sum_m=round(float(sel.inc[np.isfinite(sel.inc)].sum()), 1),
                         inc_max_m=float(sel.inc.max()), n_inc_ge500=int((sel.inc >= 500).sum())))
    st = pd.DataFrame(rows).sort_values(["n_unreachable", "inc_sum_m"], ascending=False) if rows else pd.DataFrame()
    st.to_csv(out / "structures.csv", index=False, encoding="utf-8")

    # cells
    def med(s):
        v = s.values[~np.isnan(s.values)]  # ratio is NaN where d0 = 0 (an origin on a site's node)
        return float(np.median(v)) if len(v) else np.nan
    gb = u.groupby("cell")
    cel = pd.DataFrame({
        "n_points": gb.size(),
        "d0_median_m": gb.d0.apply(med),
        "inc_median_m": gb.inc.apply(med),
        "inc_max_m": gb.inc.max(),
        "share_inc_ge500": gb.inc.apply(lambda s: float((s >= 500).mean())),
        "share_unreachable": gb.dstar.apply(lambda s: float(np.isinf(s).mean())),
        "ratio_median": gb.ratio.apply(med),
        "top_struct": gb.struct.agg(lambda s: Counter(s[s >= 0]).most_common(1)[0][0] if (s >= 0).any() else -1),
    }).reset_index()
    cel["n_points_all"] = cel.cell.map(o.groupby("cell").size())
    cel["mesh1km"] = cel.cell.str[:8]
    cel["pop_mesh1km_2020"] = cel.mesh1km.map(dict(zip(mesh["code"], mesh["pop"])))
    if len(st):
        cel["top_struct_name"] = cel.top_struct.map(dict(zip(st.struct, st.name))).fillna("")
        cel["top_struct_kinds"] = cel.top_struct.map(dict(zip(st.struct, st.kinds))).fillna("")
    cel = cel.sort_values(["inc_median_m", "inc_max_m"], ascending=False)
    cel.to_csv(out / "cells.csv", index=False, encoding="utf-8")

    fin = np.isfinite(u.inc)
    summary = dict(
        variant=a.variant, config=cfg,
        graph=dict(walk_lines=len(walk), nodes=g.n, edges=len(g.u), length_km=round(float(g.length.sum()) / 1000, 1),
                   components=int(g.comp.max() + 1), main_share=round(main_share, 4)),
        cut=cfg["cut"], kind_cut=kind_note,
        structures=dict(lines=len(struct_idx), groups=len(set(groups.values())), groups_on_paths=len(cuts),
                        groups_lengthening=int(len(st))),
        sites=dict(n=len(hz), n_snapped_nodes=int(len(np.unique(src))), snap_median_m=round(float(np.median(src_d)), 1),
                   snap_max_m=round(float(src_d.max()), 1), n_snap_over_100m=int((src_d > 100).sum())),
        origins=dict(grid_m=GRID_M, n=len(o), used=int(ok.sum()), dropped_in_water=int(in_water.sum()),
                     dropped_snap_over_100m=int(((od > SNAP_MAX_M) & ~in_water).sum()),
                     ground_min_component_m=GROUND_MIN_M, snap_median_m=round(float(np.median(od[ok])), 1), snap_max_m=round(float(od[ok].max()), 1),
                     cells=int(o.cell.nunique()), d0_inf=int(np.isinf(u.d0).sum())),
        results=dict(d0_median_m=round(float(np.median(u.d0)), 1),
                     share_lengthened=round(float((u.struct >= 0).mean()), 4),
                     share_unreachable=round(float(np.isinf(u.dstar).mean()), 4),
                     share_inc_ge500=round(float((u.inc >= 500).mean()), 4),
                     inc_median_m=round(float(np.median(u.inc[fin])), 1),
                     inc_p90_m=round(float(np.percentile(u.inc[fin], 90)), 1)),
    )
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

"""B7 (exploratory): a spot blockage anywhere on the routes (a burst pipe, a cave-in, debris), one at a time.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas \
  python -u scripts/08_spot_cut.py --radius 10 [--site-access-m 50] [--origin-access-m 50] [--buffer-m 3000]

The main run's shortest-path forest (Taito-ku origins to flood sites) is split into sections at junctions;
at each section's midpoint every walkable edge within --radius metres is removed, and the distances from all
flood sites are recomputed. An origin leaves by its snapped node or any ground node within --origin-access-m
(default 50) of its point: the 50 m grid points sample area, not doors, and the nearest node is often a
dead-end path inside a block. An origin all of whose access nodes lie inside the blockage stands in it and is
left out of that spot's result (counted). With access, a single blockage isolates an origin only when every
way out within that distance is on the blocked side, so real single-exit alleys shorter than it are missed. A spot whose radius holds a site's access node is skipped
(counted) when --site-access-m is 0: one access node per site would turn it into a single-gate site. With
--site-access-m A > 0 (default 50) a site is entered from every ground node within A metres of its point, as
if it had gates on the streets around it; the distance from those nodes to the point is not added. Writes outputs/spot_r<r>/summary.json, cells.csv, spots.csv,
bottlenecks.csv (overlapping effective spots merged) and artifacts/.../spot_r<r>/origins.parquet.
"""
import argparse
import importlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
run = importlib.import_module("02_run")
import cutdetour as cd  # noqa: E402

RATIO = 1.5
INC_M = 200.0
WIDE = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=10.0)
    ap.add_argument("--buffer-m", type=int, default=3000)
    ap.add_argument("--site-access-m", type=float, default=50.0,
                    help="a site can be entered from every ground node within this distance of its point")
    ap.add_argument("--origin-access-m", type=float, default=50.0,
                    help="an origin can leave by every ground node within this distance of its point")
    a = ap.parse_args()
    name = f"spot_r{a.radius:g}_a{a.site_access_m:g}_o{a.origin_access_m:g}" + ("" if a.buffer_m == 3000 else f"_b{a.buffer_m}")
    out = HERE.parent / "outputs" / name
    art = run.ART / name
    out.mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)

    raw = run.ART / f"raw_b{a.buffer_m}"
    c = duckdb.connect()
    c.execute("load spatial")
    lines = c.execute(f"select * exclude (g), st_aswkb(g) wkb from '{raw}/lines.parquet'").df()
    lines["geom"] = shapely.from_wkb(lines.pop("wkb").map(bytes))
    sites = c.execute(f"select * exclude (g), st_x(g) x, st_y(g) y from '{raw}/sites.parquet'").df()
    walk = lines[[run.walkable(r, False) for r in lines.itertuples()]].reset_index(drop=True)
    g = cd.build_graph(walk.geom.values)
    is_bridge = walk.bridge.map(run.is_set).values
    is_tunnel = walk.tunnel.map(run.is_set).values
    ground = cd.ground_nodes(g, np.flatnonzero(is_bridge), min_component_m=run.GROUND_MIN_M)
    hz = sites[sites.flood.fillna(False)]
    src, _ = cd.snap(g, hz[["x", "y"]].values, allowed=ground)
    access = list(src)
    if a.site_access_m > 0:
        from scipy.spatial import cKDTree
        cand = np.flatnonzero(ground & (g.comp == g.main))
        tree = cKDTree(g.xy[cand])
        for near in tree.query_ball_point(hz[["x", "y"]].values, a.site_access_m):
            access += list(cand[near])
    src_main = src
    src = np.unique(access)

    o = pd.read_parquet(run.ART / "main" / "origins.parquet")
    o = o[o.used].reset_index(drop=True)
    onode, _ = cd.snap(g, o[["x", "y"]].values, allowed=ground)
    d0_all, pred, _ = cd.multi_source(g, src, predecessors=True)
    # origin access: the snapped node, plus every ground node within --origin-access-m of the point
    cand = np.flatnonzero(ground & (g.comp == g.main))
    from scipy.spatial import cKDTree
    otree = cKDTree(g.xy[cand])
    near = otree.query_ball_point(o[["x", "y"]].values, a.origin_access_m) if a.origin_access_m > 0 else [[]] * len(o)
    acc_nodes = [np.unique(np.r_[onode[i], cand[nb]]).astype(int) for i, nb in enumerate(near)]
    acc_flat = np.concatenate(acc_nodes)
    acc_owner = np.repeat(np.arange(len(o)), [len(x) for x in acc_nodes])

    def per_origin(dist):
        best = np.full(len(o), np.inf)
        np.minimum.at(best, acc_owner, dist[acc_flat])
        return best

    d0 = per_origin(d0_all)
    assert np.isfinite(d0).all()

    fe = cd.forest_edges(pred, acc_flat)
    secs = cd.sections(g, fe)
    cutter = cd.SpotCutter(g, src)
    pair_line = {}
    for k in range(len(g.u)):
        pair_line.setdefault((min(int(g.u[k]), int(g.v[k])), max(int(g.u[k]), int(g.v[k]))), set()).add(int(g.line[k]))

    n_o = len(o)
    worst = np.zeros(n_o)
    worst_spot = np.full(n_o, -1)
    excluded_total = 0
    site_xy = g.xy[np.unique(src_main)]
    site_doorstep = 0
    rows = []
    t0 = time.time()
    for sid, (path, mid) in enumerate(secs):
        pairs = cutter.removed_pairs(mid, a.radius)
        if not (pairs & fe):
            continue
        # a blockage over a site's access node shuts the site itself: the data has one point per site and no
        # gates, so this would read every school as having a single entrance. Left out and counted.
        if a.site_access_m == 0 and (np.hypot(*(site_xy - mid).T) <= a.radius).any():
            site_doorstep += 1
            continue
        d = per_origin(cutter.distances(pairs))
        # an origin all of whose access nodes lie inside the blockage stands in it: left out (counted)
        inside = np.hypot(*(g.xy[acc_flat] - mid).T) <= a.radius
        n_out = np.bincount(acc_owner, weights=~inside, minlength=len(o))
        at_block = n_out == 0
        excluded_total += int(at_block.sum())
        inc = d - d0
        inc[at_block] = 0.0
        hit = inc > 1e-6
        better = hit & (inc > worst)
        worst[better] = inc[better]
        worst_spot[better] = sid
        if hit.any():
            lines_hit = {li for p in pairs for li in pair_line[p]}
            names = Counter(n for li in lines_hit for n in (walk.name.values[li], walk.bridge_name.values[li])
                            if isinstance(n, str) and n)
            rows.append(dict(spot=sid, x=mid[0], y=mid[1], n_lengthened=int(hit.sum()),
                             n_unreachable=int(np.isinf(inc[hit]).sum()),
                             inc_sum_m=round(float(inc[hit & np.isfinite(inc)].sum()), 1),
                             inc_max_m=float(inc[hit].max()), n_excluded=int(at_block.sum()),
                             bridge=bool(is_bridge[list(lines_hit)].any()),
                             tunnel=bool(is_tunnel[list(lines_hit)].any()),
                             highways="|".join(sorted({str(walk.highway.values[li]) for li in lines_hit})),
                             name=names.most_common(1)[0][0] if names else ""))
        if sid % 1000 == 0:
            print(f"{sid}/{len(secs)} sections, {time.time() - t0:.0f} s", flush=True)

    sp = pd.DataFrame(rows)
    to_ll = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
    if len(sp):
        sp["lon"], sp["lat"] = to_ll.transform(sp.x.values, sp.y.values)
        # merge effective spots whose blockages overlap into one bottleneck section
        xy = sp[["x", "y"]].values
        tree = shapely.STRtree(shapely.points(xy))
        l, r = tree.query(shapely.points(xy), predicate="dwithin", distance=2 * a.radius)
        _, lab = connected_components(csr_matrix((np.ones(len(l)), (l, r)), shape=(len(sp), len(sp))), directed=False)
        sp["bottleneck"] = lab
    sp.to_csv(out / "spots.csv", index=False, encoding="utf-8")

    o["d0"] = d0
    o["inc"] = worst
    o["dstar"] = d0 + worst
    o["ratio"] = np.where(d0 > 0, o.dstar / np.where(d0 > 0, d0, 1), np.nan)
    o["spot"] = worst_spot
    o["bottleneck"] = o.spot.map(dict(zip(sp.spot, sp.bottleneck))) if len(sp) else -1
    o.to_parquet(art / "origins.parquet")

    flag = (o.ratio >= RATIO) | np.isinf(o.inc)
    bn = o[o.spot >= 0].groupby("bottleneck").agg(n_origins_worst=("x", "size"),
                                                   n_unreachable=("inc", lambda s: int(np.isinf(s).sum())),
                                                   inc_max_m=("inc", "max"),
                                                   n_ratio_ge_15=("ratio", lambda s: int((s >= RATIO).sum())))
    if len(sp):
        agg = sp.groupby("bottleneck").agg(spots=("spot", "size"), n_lengthened_max=("n_lengthened", "max"),
                                           bridge=("bridge", "any"), tunnel=("tunnel", "any"),
                                           lon=("lon", "mean"), lat=("lat", "mean"),
                                           name=("name", lambda s: Counter(x for x in s if x).most_common(1)[0][0]
                                                 if any(s) else ""),
                                           highways=("highways", lambda s: "|".join(sorted(set("|".join(s).split("|"))))))
        bn = agg.join(bn, how="left").fillna({"n_origins_worst": 0, "n_unreachable": 0, "n_ratio_ge_15": 0})
        bn["wide"] = bn.n_lengthened_max >= WIDE
        bn = bn.sort_values(["n_unreachable", "n_ratio_ge_15", "n_lengthened_max"], ascending=False)
    bn.to_csv(out / "bottlenecks.csv", encoding="utf-8")

    gb = o.groupby("cell")
    cel = pd.DataFrame({"n_points": gb.size(),
                        "share_ratio_ge15_or_unreachable": gb.apply(lambda t: float(((t.ratio >= RATIO) | np.isinf(t.inc)).mean()), include_groups=False),
                        "share_unreachable": gb.inc.apply(lambda s: float(np.isinf(s).mean())),
                        "share_inc_ge200": gb.inc.apply(lambda s: float((s >= INC_M).mean())),
                        "inc_median_m": gb.inc.median(), "inc_max_m": gb.inc.max(),
                        "d0_median_m": gb.d0.median(),
                        "top_bottleneck": gb.bottleneck.agg(lambda s: Counter(s[s >= 0]).most_common(1)[0][0]
                                                            if (s >= 0).any() else -1)}).reset_index()
    cel = cel.sort_values(["share_ratio_ge15_or_unreachable", "share_unreachable", "inc_max_m"], ascending=False)
    cel.to_csv(out / "cells.csv", index=False, encoding="utf-8")

    fin = np.isfinite(o.inc)
    summary = dict(
        radius_m=a.radius, buffer_m=a.buffer_m, origin_access_m=a.origin_access_m,
        origin_access_nodes_median=float(np.median([len(x) for x in acc_nodes])), site_access_m=a.site_access_m, site_access_nodes=int(len(src)), graph=dict(nodes=g.n, edges=len(g.u)),
        forest_edges=len(fe), sections=len(secs), spots_effective=int(len(sp)),
        bottlenecks=int(sp.bottleneck.nunique()) if len(sp) else 0,
        bottlenecks_wide=int(bn.wide.sum()) if len(sp) else 0,
        origins=n_o, origin_spot_pairs_excluded=excluded_total, spots_skipped_site_doorstep=site_doorstep,
        share_lengthened=round(float((o.spot >= 0).mean()), 4),
        share_unreachable=round(float(np.isinf(o.inc).mean()), 4),
        share_ratio_ge15_or_unreachable=round(float(flag.mean()), 4),
        share_inc_ge200=round(float((o.inc >= INC_M).mean()), 4),
        inc_median_m=round(float(np.median(o.inc[fin])), 1), inc_p90_m=round(float(np.percentile(o.inc[fin], 90)), 1),
        inc_max_finite_m=round(float(o.inc[fin].max()), 1),
        cells_any_flag=int((cel.share_ratio_ge15_or_unreachable > 0).sum()), cells=int(len(cel)),
        seconds=round(time.time() - t0, 1))
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

"""B8 (exploratory): how many separate approaches lead into each flood site.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas \
  python -u scripts/11_site_approaches.py [--site-access-m 50]

Same graph, sites, access and origins as 08_spot_cut.py with its defaults (buffer 3 km, site and origin access
50 m). A site is entered from its access nodes S (the snapped node and every ground node within 50 m of its point).
For R in 50, 100, 200 m (L = 200 m beyond): k_e, the most edge-disjoint walks from S to the outside, and k, the cut
edges grouped within 20 m (cutdetour.approaches). For each R, whether one 10 m disk closes the site
(cutdetour.single_gate). The sites are the flood sites that some Taito-ku origin walks to in normal times (its
nearest by the B7 baseline) and the flood sites inside Taito-ku. The share of each site's origins that the B7 main
run (spot_r10_a50_o50) flags (ratio 1.5 or more, or cut off) is joined for comparison.

Writes outputs/site_approaches/sites.csv, cut_groups.csv, summary.json (site_approaches_a<A>/ when --site-access-m
is not 50; the destinations and the B7 shares stay those of the 50 m run).
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
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
run = importlib.import_module("02_run")
import cutdetour as cd  # noqa: E402

BUFFER_M = 3000
SITE_ACCESS_M = 50.0
ORIGIN_ACCESS_M = 50.0
RS = (50.0, 100.0, 200.0)
MAIN_R = 100.0
L_M = 200.0
MERGE_M = 20.0
DISK_M = 10.0
B7 = "spot_r10_a50_o50"
MIN_CATCH = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-access-m", type=float, default=SITE_ACCESS_M,
                    help="access nodes used for counting approaches (destinations always use 50 m, as in B7)")
    args = ap.parse_args()
    a_cnt = args.site_access_m
    out = HERE.parent / "outputs" / ("site_approaches" if a_cnt == SITE_ACCESS_M else f"site_approaches_a{a_cnt:g}")
    out.mkdir(parents=True, exist_ok=True)
    raw = run.ART / f"raw_b{BUFFER_M}"
    c = duckdb.connect()
    c.execute("load spatial")
    lines = c.execute(f"select * exclude (g), st_aswkb(g) wkb from '{raw}/lines.parquet'").df()
    lines["geom"] = shapely.from_wkb(lines.pop("wkb").map(bytes))
    sites = c.execute(f"select * exclude (g), st_x(g) x, st_y(g) y from '{raw}/sites.parquet'").df()
    taito = shapely.from_wkb(bytes(c.execute(f"select st_aswkb(g) from '{raw}/taito.parquet'").fetchall()[0][0]))
    walk = lines[[run.walkable(r, False) for r in lines.itertuples()]].reset_index(drop=True)
    g = cd.build_graph(walk.geom.values)
    is_bridge = walk.bridge.map(run.is_set).values
    ground = cd.ground_nodes(g, np.flatnonzero(is_bridge), min_component_m=run.GROUND_MIN_M)
    hz = sites[sites.flood.fillna(False)].reset_index(drop=True)
    snapped, _ = cd.snap(g, hz[["x", "y"]].values, allowed=ground)
    cand = np.flatnonzero(ground & (g.comp == g.main))
    tree = cKDTree(g.xy[cand])
    access = [np.unique(np.r_[snapped[i], cand[nb]]).astype(int)
              for i, nb in enumerate(tree.query_ball_point(hz[["x", "y"]].values, SITE_ACCESS_M))]
    # an access node shared by two sites belongs to the one with the nearer point
    owner = {}
    for i, S in enumerate(access):
        for x in S:
            dd = float(np.hypot(*(g.xy[x] - hz.loc[i, ["x", "y"]].values.astype(float))))
            if x not in owner or dd < owner[x][1]:
                owner[int(x)] = (i, dd)
    src = np.unique(np.concatenate(access))
    count_access = access if a_cnt == SITE_ACCESS_M else [
        np.unique(np.r_[snapped[i], cand[nb]]).astype(int) if a_cnt > 0 else np.array([snapped[i]])
        for i, nb in enumerate(tree.query_ball_point(hz[["x", "y"]].values, max(a_cnt, 1e-9)))]

    # normal-time destination of every origin, as in 08_spot_cut.py
    o = pd.read_parquet(run.ART / "main" / "origins.parquet")
    o = o[o.used].reset_index(drop=True)
    onode, _ = cd.snap(g, o[["x", "y"]].values, allowed=ground)
    d0_all, _, from_src = cd.multi_source(g, src, predecessors=True)
    near = tree.query_ball_point(o[["x", "y"]].values, ORIGIN_ACCESS_M)
    dest = np.empty(len(o), int)
    for i, nb in enumerate(near):
        acc = np.unique(np.r_[onode[i], cand[nb]]).astype(int)
        best = acc[np.argmin(d0_all[acc])]
        dest[i] = owner[int(from_src[best])][0]
    b7 = pd.read_parquet(run.ART / B7 / "origins.parquet")
    assert len(b7) == len(o) and np.allclose(b7.x.values, o.x.values) and np.allclose(b7.y.values, o.y.values)
    flagged = ((b7.ratio >= 1.5) | np.isinf(b7.inc)).values
    catch = pd.DataFrame({"site": dest, "flag": flagged}).groupby("site").agg(catchment=("flag", "size"),
                                                                             flagged=("flag", "sum"))

    in_taito = np.array([taito.contains(shapely.Point(x, y)) for x, y in zip(hz.x, hz.y)])
    todo = sorted(set(catch.index) | set(np.flatnonzero(in_taito)))
    to_ll = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
    rows, groups = [], []
    t0 = time.time()
    for i in todo:
        S = count_access[i]
        row = dict(site=int(i), common_id=hz.common_id[i], name=hz.name[i], municipality=hz.municipality[i],
                   x=float(hz.x[i]), y=float(hz.y[i]),
                   in_taito=bool(in_taito[i]), access_nodes=int(len(S)),
                   catchment=int(catch.catchment.get(i, 0)), flagged=int(catch.flagged.get(i, 0)))
        for R in RS:
            a = cd.approaches(g, S, R=R, L=L_M, merge_m=MERGE_M)
            closes, skipped, spots = cd.single_gate(g, S, R=R, L=L_M, r=DISK_M, return_spots=True)
            tag = f"r{R:g}"
            row.update({f"k_e_{tag}": a["k_e"], f"k_{tag}": a["k"], f"closes_{tag}": bool(closes),
                        f"closing_disks_{tag}": int(len(spots)), f"skipped_disks_{tag}": int(skipped)})
            cut = np.asarray(a["cut"], dtype=int)
            lab = np.asarray(a["groups"], dtype=int)
            for gi in range(a["k"]):
                e = cut[lab == gi]
                pts = np.vstack([g.xy[g.u[e]], g.xy[g.v[e]]])
                cx, cy = pts.mean(axis=0)
                names = Counter(n for li in g.line[e] for n in (walk.name.values[li],) if isinstance(n, str) and n)
                lon, lat = to_ll.transform(cx, cy)
                groups.append(dict(site=int(i), R=R, group=gi, edges=int(len(e)), x=cx, y=cy, lon=lon, lat=lat,
                                   name=names.most_common(1)[0][0] if names else "",
                                   highways="|".join(sorted({str(walk.highway.values[li]) for li in g.line[e]}))))
        rows.append(row)
    print(f"{len(todo)} sites, {time.time() - t0:.0f} s", flush=True)

    t = pd.DataFrame(rows)
    t["flagged_share"] = np.where(t.catchment > 0, t.flagged / t.catchment.clip(lower=1), np.nan)
    t = t.sort_values([f"k_r{MAIN_R:g}", "catchment"], ascending=[True, False])
    t.to_csv(out / "sites.csv", index=False, encoding="utf-8")
    gr = pd.DataFrame(groups)
    gr.to_csv(out / "cut_groups.csv", index=False, encoding="utf-8")

    summary = dict(sites=int(len(t)), sites_with_catchment=int((t.catchment > 0).sum()),
                   sites_in_taito=int(t.in_taito.sum()), R_main_m=MAIN_R, L_m=L_M, merge_m=MERGE_M, disk_m=DISK_M,
                   site_access_m=a_cnt, destination_access_m=SITE_ACCESS_M, origins=int(len(o)))
    for R in RS:
        tag = f"r{R:g}"
        k, cl = t[f"k_{tag}"], t[f"closes_{tag}"]
        summary[tag] = dict(k_counts={str(int(x)): int(n) for x, n in k.value_counts().sort_index().items()},
                            k1=int((k == 1).sum()), closes=int(cl.sum()),
                            k1_and_closes=int(((k == 1) & cl).sum()), k1_not_closes=int(((k == 1) & ~cl).sum()),
                            closes_k_ge2=int(((k >= 2) & cl).sum()),
                            k1_catchment=int(t.catchment[k == 1].sum()))
        big = t[t.catchment >= MIN_CATCH]
        if len(big) > 2:
            rho = spearmanr(big[f"k_{tag}"], big.flagged_share).statistic
            summary[tag]["spearman_k_flagged_share"] = round(float(rho), 3)
            summary[tag]["spearman_sites"] = int(len(big))
            summary[tag]["flagged_share_median_k1"] = (round(float(big.flagged_share[big[f"k_{tag}"] == 1].median()), 4)
                                                      if (big[f"k_{tag}"] == 1).any() else None)
            summary[tag]["flagged_share_median_k_ge2"] = round(float(big.flagged_share[big[f"k_{tag}"] >= 2].median()), 4)
    summary["seconds"] = round(time.time() - t0, 1)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(t.head(25).to_string())


if __name__ == "__main__":
    main()

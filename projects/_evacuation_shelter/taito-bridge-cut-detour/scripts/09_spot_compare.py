"""Compare the spot-blockage variants (B7) and make the edge table for the map.

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with shapely --with scipy python scripts/09_spot_compare.py

Writes outputs/spot_compare.csv (one row per variant: shares, top-5 cells and their overlap with the main
variant spot_r10_a50_o50, Spearman of the cell shares), outputs/spot_compare_summary.json, and
artifacts/.../spot_r10_a50_o50/spot_edges.parquet: every walkable way of the tree table, with n_flagged = the
origins whose worst blockage (a disk of the run's radius) touches the way and whose route then grows 1.5 times
or more or is cut off.
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"
ART = HERE.parents[3] / "artifacts/_evacuation_shelter/taito-bridge-cut-detour"
MAIN = "spot_r10_a50_o50"
TOP = 5


def main():
    variants = sorted(p.name for p in OUT.glob("spot_r*") if (p / "summary.json").exists())
    mc = pd.read_csv(OUT / MAIN / "cells.csv", dtype={"cell": str})
    key = "share_ratio_ge15_or_unreachable"
    m_top = list(mc.cell[:TOP])
    rows = []
    for v in variants:
        s = json.loads((OUT / v / "summary.json").read_text(encoding="utf-8"))
        c = pd.read_csv(OUT / v / "cells.csv", dtype={"cell": str})
        j = mc.merge(c, on="cell", suffixes=("_m", "_v"))
        rows.append(dict(variant=v, radius_m=s["radius_m"], site_access_m=s.get("site_access_m", 0),
                         origin_access_m=s.get("origin_access_m", 0), sections=s["sections"],
                         bottlenecks=s["bottlenecks"], bottlenecks_wide=s["bottlenecks_wide"],
                         share_unreachable=s["share_unreachable"], share_flag=s[key],
                         share_inc_ge200=s["share_inc_ge200"], inc_median_m=s["inc_median_m"],
                         inc_p90_m=s["inc_p90_m"], top5=" ".join(c.cell[:TOP]),
                         top5_common=len(set(c.cell[:TOP]) & set(m_top)),
                         spearman=round(float(spearmanr(j[key + "_m"], j[key + "_v"]).statistic), 3)))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "spot_compare.csv", index=False, encoding="utf-8")
    print(t.drop(columns=["top5"]).to_string())

    # edge table for the map of the main variant
    s = json.loads((OUT / MAIN / "summary.json").read_text(encoding="utf-8"))
    o = pd.read_parquet(ART / MAIN / "origins.parquet")
    sp = pd.read_csv(OUT / MAIN / "spots.csv")
    flagged = o[((o.ratio >= 1.5) | np.isinf(o.inc)) & (o.spot >= 0)]
    per_spot = flagged.groupby("spot").size()
    c = duckdb.connect()
    c.execute("load spatial")
    e = c.execute(f"select n_origins, lengthening, name, st_aswkb(geometry) wkb from "
                  f"'{ART / 'main' / 'tree_edges.parquet'}'").df()
    geoms = shapely.from_wkb(e.wkb.map(bytes))
    tree = shapely.STRtree(geoms)
    spx = sp.set_index("spot").loc[per_spot.index]
    pts = shapely.points(spx[["x", "y"]].values)
    pi, ei = tree.query(pts, predicate="dwithin", distance=s["radius_m"])
    n_flag = np.zeros(len(e))
    np.add.at(n_flag, ei, per_spot.values[pi])
    e["n_flagged"] = n_flag
    # name the 8 spots that flag the most origins, on one way each
    top_spots = per_spot.sort_values(ascending=False).head(8)
    e["label"] = None
    for sid, n in top_spots.items():
        p = shapely.Point(sp.set_index("spot").loc[sid, ["x", "y"]].values)
        k = int(tree.nearest(p))
        nm = sp.set_index("spot").loc[sid, "name"]
        e.loc[k, "label"] = (nm if isinstance(nm, str) and nm else "(名前なし)") + f" {n}"
    e["top"] = e.label.notna()
    c.register("e", e.drop(columns=["wkb"]).assign(wkb=e.wkb))
    c.execute(f"copy (select n_flagged, top, label, st_geomfromwkb(wkb) geometry from e) "
              f"to '{ART / MAIN / 'spot_edges.parquet'}' (format parquet)")
    # how far the worst blockage of each flagged origin lies from the nearest flood site point
    sites = pd.read_csv(ART / "main" / "sites_xy.csv")
    from scipy.spatial import cKDTree
    spt = sp.set_index("spot").loc[flagged.spot, ["x", "y"]].values
    dsite, _ = cKDTree(sites[["x", "y"]].values).query(spt)
    near_site = {f"within_{m}m": round(float((dsite <= m).mean()), 4) for m in (100, 200, 300)}
    summary = dict(main=MAIN, variants=len(t), flagged_origins=int(len(flagged)),
                   flagged_worst_spot_to_nearest_site=near_site,
                   flagged_worst_spot_to_nearest_site_median_m=round(float(np.median(dsite)), 1),
                   spots_flagging=int(len(per_spot)), ways_with_flag=int((n_flag > 0).sum()),
                   n_flagged_max=int(n_flag.max()),
                   top_spots={str(k): int(v) for k, v in top_spots.items()},
                   top5_overlap=dict(zip(t.variant, t.top5_common.astype(int))))
    (OUT / "spot_compare_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

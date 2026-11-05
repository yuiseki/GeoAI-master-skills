"""Exploratory (B6): which origins sit where nobody lives, and the cell table restricted to origins near buildings.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pandas --with pyarrow python scripts/05_origin_context.py

The 50 m grid weights origins by area, so parks, cemeteries, the zoo and rail yards count as much as housing.
This flags every origin of the main run that lies in a leisure=park, landuse=cemetery, tourism=zoo or
landuse=railway polygon of OSM, and whether a building footprint lies within 25 m. It writes
outputs/main/origin_context.json (counts) and outputs/main/cells_near_buildings.csv (the cells table over the
origins within 25 m of a building and outside those polygons). OSM buildings are not a population count.
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_evacuation_shelter/taito-bridge-cut-detour"
OUT = HERE.parent / "outputs" / "main"
OSM = "hf://datasets/yuiseki/osm-japan-src-2026-08@9a9b4a77e89e28a66bf15781644a16b63501f622/parquet/planet_osm_polygon.parquet"
NEAR_M = 25.0


def main():
    c = duckdb.connect()
    c.execute("install spatial; load spatial; install httpfs; load httpfs; set threads=4")
    raw = ART / "raw_b5000"
    c.execute(f"create table taito as select g from '{raw}/taito.parquet'")
    xmin, ymin, xmax, ymax = c.execute("""select st_xmin(b), st_ymin(b), st_xmax(b), st_ymax(b) from
        (select st_transform(st_buffer(g, 100), 'EPSG:6677', 'EPSG:3857', always_xy := true) b from taito)""").fetchall()[0]
    bb = f"bbox.xmin <= {xmax} and bbox.xmax >= {xmin} and bbox.ymin <= {ymax} and bbox.ymax >= {ymin}"
    rows = c.execute(f"""select osm_id, building, leisure, landuse, tourism,
        st_aswkb(st_transform(way, 'EPSG:3857', 'EPSG:6677', always_xy := true)) wkb from '{OSM}'
        where {bb} and (building is not null or leisure = 'park' or landuse in ('cemetery', 'railway')
                        or tourism = 'zoo')""").df()
    geoms = shapely.from_wkb(rows.wkb.map(bytes))
    is_bld = rows.building.notna().values
    kind = np.select([rows.tourism.eq("zoo"), rows.landuse.eq("cemetery"), rows.landuse.eq("railway"),
                      rows.leisure.eq("park")], ["zoo", "cemetery", "railway", "park"], "")

    o = pd.read_parquet(ART / "main" / "origins.parquet")
    o = o[o.used].copy()
    pts = shapely.points(o[["x", "y"]].values)
    btree = shapely.STRtree(geoms[is_bld])
    near_b = np.zeros(len(o), bool)
    hit, _ = btree.query(pts, predicate="dwithin", distance=NEAR_M)
    near_b[hit] = True
    o["near_building"] = near_b
    o["nonres"] = ""
    for k in ["zoo", "cemetery", "railway", "park"]:
        t = shapely.STRtree(geoms[kind == k])
        hit, _ = t.query(pts, predicate="within")
        sel = np.zeros(len(o), bool)
        sel[hit] = True
        o.loc[sel & (o.nonres == ""), "nonres"] = k

    lengthened = o.struct >= 0
    summary = dict(
        buildings=int(is_bld.sum()), polygons={k: int((kind == k).sum()) for k in ["zoo", "cemetery", "railway", "park"]},
        origins=len(o), near_building=int(near_b.sum()),
        nonres_counts=o.nonres.value_counts().to_dict(),
        lengthened=int(lengthened.sum()),
        lengthened_by_nonres=o[lengthened].nonres.value_counts().to_dict(),
        lengthened_in_nonres_total=int((lengthened & (o.nonres != "")).sum()),
        lengthened_near_building_and_res=int((lengthened & near_b & (o.nonres == "")).sum()),
        kept=int((near_b & (o.nonres == "")).sum()),
    )
    k = o[near_b & (o.nonres == "")]
    k["inc"] = k.dstar - k.d0
    gb = k.groupby("cell")
    cel = pd.DataFrame({"n_points": gb.size(), "d0_median_m": gb.d0.median(), "inc_median_m": gb.inc.median(),
                        "inc_max_m": gb.inc.max(), "share_lengthened": gb.struct.apply(lambda s: float((s >= 0).mean())),
                        "share_inc_ge100": gb.inc.apply(lambda s: float((s >= 100).mean()))}).reset_index()
    cel = cel.sort_values(["inc_median_m", "inc_max_m"], ascending=False)
    cel.to_csv(OUT / "cells_near_buildings.csv", index=False, encoding="utf-8")
    summary["cells_near_buildings_median_gt0"] = int((cel.inc_median_m > 0).sum())
    summary["max_inc_kept_m"] = round(float(k.inc.max()), 1)
    (OUT / "origin_context.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(cel.head(10).to_string())


if __name__ == "__main__":
    main()

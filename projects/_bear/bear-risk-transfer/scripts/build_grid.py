"""Build the 100 m grid over Akita prefecture (EPSG:6678) from the municipality polygons of jp-admin-2026-09.

A cell belongs to the prefecture when its centre is inside a municipality polygon; it is labelled with that
municipality (the first polygon in code order, where slivers overlap). Writes:
    grid.json        the grid (origin, size, nx, ny, crs) and the municipality codes in label order
    grid_mask.npz    `muni`: [ny, nx] int16, the municipality label of each cell, -1 outside the prefecture
    cells.parquet    one row per cell in the prefecture: cell (= iy*nx + ix), ix, iy, x, y, lon, lat, code5

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
        --with shapely --with pyproj --with pandas --with pyarrow python build_grid.py OUT_DIR
"""

import json
import sys

import numpy as np

from grid import Grid

ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"


def cells_inside(grid, polygons):
    """[ny, nx] label of the polygon that contains each cell centre (first one wins), -1 if none."""
    import shapely

    x, y = grid.centres()
    out = np.full(x.shape, -1, dtype=np.int16)
    for k, poly in enumerate(polygons):
        shapely.prepare(poly)
        inside = shapely.contains_xy(poly, x, y) & (out == -1)
        out[inside] = k
    return out


def main():
    import duckdb
    import pandas as pd
    import pyproj
    import shapely

    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--pref", required=True, help="2-digit prefecture code, e.g. 21")
    ap.add_argument("--crs", required=True, help="the plane rectangular CS of the area, e.g. EPSG:6675")
    ap.add_argument("--code5", default=None, help="only this municipality (5-digit code)")
    a = ap.parse_args()
    out_dir, CRS = a.out_dir, a.crs
    only = "" if a.code5 is None else f" AND code5 = '{a.code5}'"
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    rows = con.execute(f"""SELECT code5, name, ST_AsWKB(geometry) FROM read_parquet('{ADMIN}')
                           WHERE pref_code = '{a.pref}' AND ward IS NULL AND geometry IS NOT NULL{only} ORDER BY code5""").fetchall()
    tr = pyproj.Transformer.from_crs("EPSG:4612", CRS, always_xy=True)
    def to_6678(coords):
        return np.column_stack(tr.transform(coords[:, 0], coords[:, 1]))

    polys = [shapely.transform(shapely.from_wkb(bytes(w)), to_6678) for _, _, w in rows]
    codes = [r[0] for r in rows]
    union = shapely.union_all(polys)
    g = Grid.from_bounds(*union.bounds, size=100.0)
    print(f"{len(polys)} municipalities; grid {g.nx} x {g.ny} cells of {g.size:.0f} m; origin ({g.x0}, {g.y0})")
    muni = cells_inside(g, polys)
    n = int((muni >= 0).sum())
    area_cells = n * g.size ** 2 / 1e6
    area_poly = sum(p.area for p in polys) / 1e6
    print(f"cells in the prefecture: {n} ({area_cells:.1f} km2); polygon area {area_poly:.1f} km2 (in {CRS})")

    iy, ix = np.nonzero(muni >= 0)
    xc = g.x0 + (ix + 0.5) * g.size
    yc = g.y0 + (iy + 0.5) * g.size
    back = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    lon, lat = back.transform(xc, yc)
    df = pd.DataFrame({"cell": iy * g.nx + ix, "ix": ix, "iy": iy, "x": xc, "y": yc, "lon": lon, "lat": lat,
                       "code5": np.array(codes)[muni[iy, ix]]})
    df.to_parquet(f"{out_dir}/cells.parquet")
    np.savez_compressed(f"{out_dir}/grid_mask.npz", muni=muni)
    json.dump({**g.to_dict(CRS), "codes": codes, "names": [r[1] for r in rows], "cells_in_prefecture": n},
              open(f"{out_dir}/grid.json", "w"), ensure_ascii=False, indent=1)
    print("cells per municipality (top 5):", df.code5.value_counts().head().to_dict())
    print("wrote", out_dir)


if __name__ == "__main__":
    main()

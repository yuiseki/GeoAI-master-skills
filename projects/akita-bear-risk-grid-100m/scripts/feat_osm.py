"""Distances to roads, rivers and buildings, and building counts, per 100 m cell, from the OSM Japan snapshot.

Reads only the bounding box of the grid (plus a 5 km margin) from osm-japan-src-2026-08 (EPSG:3857), moves
the geometries to EPSG:6678, marks the cells each line passes through (points every 20 m along it) and the
cells that hold a building's centroid, and takes the Euclidean distance (m, centre to centre) to the nearest
marked cell on a grid padded by the margin, so features just across the prefecture border count. Writes
`osm.npz`: d_road_major, d_road, d_track, d_river, d_stream, d_building (m), n_building (count in the cell).

Road classes: major = motorway, trunk, primary, secondary, tertiary (and their links); road = those plus
unclassified, residential, living_street, service; track = track, path, footway, bridleway.
River = waterway river or canal; stream = waterway stream.

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
        --with scipy --with shapely --with pyproj python feat_osm.py ART_DIR
"""

import json
import sys
import time

import numpy as np

from grid import CRS, Grid

REV = "9a9b4a77e89e28a66bf15781644a16b63501f622"
BASE = f"hf://datasets/yuiseki/osm-japan-src-2026-08@{REV}/parquet/"
MAJOR = ["motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"]
MINOR = ["unclassified", "residential", "living_street", "service"]
TRACK = ["track", "path", "footway", "bridleway"]
MARGIN_CELLS = 50  # 5 km


def padded(grid, k):
    return Grid(grid.x0 - k * grid.size, grid.y0 - k * grid.size, grid.nx + 2 * k, grid.ny + 2 * k, grid.size), k


def crop(arr, k, grid):
    return arr[k:k + grid.ny, k:k + grid.nx]


def line_presence(grid, lines, step=20.0):
    import shapely

    pres = np.zeros((grid.ny, grid.nx), dtype=bool)
    if len(lines) == 0:
        return pres
    dense = shapely.segmentize(np.asarray(lines, dtype=object), step)
    xy = shapely.get_coordinates(dense)
    ix, iy, ok = grid.index(xy[:, 0], xy[:, 1])
    pres[iy[ok], ix[ok]] = True
    return pres


def distance_m(presence, size):
    from scipy.ndimage import distance_transform_edt

    if not presence.any():
        return np.full(presence.shape, np.nan)
    return distance_transform_edt(~presence) * size


def main():
    import duckdb
    import pyproj
    import shapely

    art = sys.argv[1]
    meta = json.load(open(f"{art}/grid.json"))
    g = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    pg, k = padded(g, MARGIN_CELLS)
    # the padded grid's corners in EPSG:3857, as numbers for the bbox filter
    to3857 = pyproj.Transformer.from_crs(CRS, "EPSG:3857", always_xy=True)
    cx = [pg.x0, pg.x0 + pg.nx * pg.size]
    cy = [pg.y0, pg.y0 + pg.ny * pg.size]
    X, Y = to3857.transform([cx[0], cx[0], cx[1], cx[1]], [cy[0], cy[1], cy[0], cy[1]])
    xmin, xmax, ymin, ymax = min(X), max(X), min(Y), max(Y)
    where = f"bbox.xmin <= {xmax} AND bbox.xmax >= {xmin} AND bbox.ymin <= {ymax} AND bbox.ymax >= {ymin}"
    print(f"bbox EPSG:3857 x {xmin:.0f}..{xmax:.0f}, y {ymin:.0f}..{ymax:.0f}")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    tr = pyproj.Transformer.from_crs("EPSG:3857", CRS, always_xy=True)

    def to_6678(coords):
        return np.column_stack(tr.transform(coords[:, 0], coords[:, 1]))

    t0 = time.time()
    lines = con.execute(f"""SELECT highway, waterway, ST_AsWKB(way) FROM read_parquet('{BASE}planet_osm_line.parquet')
                            WHERE {where} AND (highway IS NOT NULL OR waterway IN ('river', 'canal', 'stream'))""").fetchall()
    print(f"lines read: {len(lines)} in {time.time() - t0:.0f} s")
    geoms = shapely.transform(shapely.from_wkb([bytes(r[2]) for r in lines]), to_6678)
    hw = np.array([r[0] for r in lines], dtype=object)
    ww = np.array([r[1] for r in lines], dtype=object)
    out = {}
    groups = {
        "road_major": np.isin(hw, MAJOR),
        "road": np.isin(hw, MAJOR + MINOR),
        "track": np.isin(hw, TRACK),
        "river": np.isin(ww, ["river", "canal"]),
        "stream": ww == "stream",
    }
    for name, sel in groups.items():
        pres = line_presence(pg, geoms[sel])
        out[f"d_{name}"] = crop(distance_m(pres, pg.size), k, g).astype(np.float32)
        print(f"  {name}: {int(sel.sum())} lines, {int(crop(pres, k, g).sum())} cells marked in the grid")

    t0 = time.time()
    b = con.execute(f"""SELECT ST_X(c), ST_Y(c) FROM (SELECT ST_Centroid(way) AS c FROM read_parquet('{BASE}planet_osm_polygon.parquet')
                        WHERE {where} AND building IS NOT NULL)""").fetchnumpy()
    bx, by = tr.transform(b[list(b.keys())[0]], b[list(b.keys())[1]])
    print(f"building centroids read: {len(bx)} in {time.time() - t0:.0f} s (multipolygon parts counted separately)")
    cnt, off = pg.sum_into(bx, by)
    out["n_building"] = crop(cnt, k, g).astype(np.float32)
    out["d_building"] = crop(distance_m(cnt > 0, pg.size), k, g).astype(np.float32)
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    inside = muni >= 0
    print("buildings in prefecture cells:", int(out["n_building"][inside].sum()), "| off the padded grid:", off)
    for kname, v in out.items():
        vv = v[inside]
        print(f"  {kname}: NaN {int(np.isnan(vv).sum())}, median {np.nanmedian(vv):.0f}, p90 {np.nanpercentile(vv, 90):.0f}, max {np.nanmax(vv):.0f}")
    np.savez_compressed(f"{art}/osm.npz", **out)
    print("wrote osm.npz")


if __name__ == "__main__":
    main()

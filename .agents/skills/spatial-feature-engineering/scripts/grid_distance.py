"""Distance (m, centre to centre) from every cell of a regular square grid to the nearest cell that holds a feature:
a line (road, river) marked in every cell it passes through, or a point (building centroid) in its cell.

The distance is taken on the grid padded by a margin, so that a feature just across the edge of the area counts,
and then cut back to the grid. Cells that hold the feature get 0. With no feature on the padded grid the distance is
NaN, not 0. The resolution is the cell: a feature anywhere in a cell is at that cell's centre.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj python grid_distance.py \\
        FEATURES.parquet GEOM_COL SRC_CRS GRID.json OUT.npz [--where "highway IS NOT NULL"] [--pad 50] [--step 20]

FEATURES may be a GeoParquet (a GEOMETRY column) or a Parquet with WKB in a BLOB column; a remote path is read
with httpfs. GRID.json holds x0, y0, nx, ny, size and crs. OUT.npz gets `distance` and `count` (features per cell).
"""

import argparse
import json

import numpy as np


class GridSpec:
    def __init__(self, x0, y0, nx, ny, size):
        self.x0, self.y0, self.nx, self.ny, self.size = float(x0), float(y0), int(nx), int(ny), float(size)

    def index(self, x, y):
        ix = np.floor((np.asarray(x) - self.x0) / self.size).astype(np.int64)
        iy = np.floor((np.asarray(y) - self.y0) / self.size).astype(np.int64)
        return ix, iy, (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)


def padded(grid, k):
    return GridSpec(grid.x0 - k * grid.size, grid.y0 - k * grid.size, grid.nx + 2 * k, grid.ny + 2 * k, grid.size)


def crop(arr, k, grid):
    return arr[k:k + grid.ny, k:k + grid.nx]


def line_presence(grid, lines, step=20.0):
    """[ny, nx] bool: the cells a line passes through, from points every `step` along it (step well under the cell)."""
    import shapely

    pres = np.zeros((grid.ny, grid.nx), dtype=bool)
    if len(lines) == 0:
        return pres
    parts = shapely.get_parts(np.asarray(lines, dtype=object))
    # a part of zero length (its points all the same) cannot be segmentized: it marks the cell of its point
    flat = shapely.length(parts) == 0
    xy = np.vstack([shapely.get_coordinates(shapely.segmentize(parts[~flat], step)), shapely.get_coordinates(parts[flat])])
    ix, iy, ok = grid.index(xy[:, 0], xy[:, 1])
    pres[iy[ok], ix[ok]] = True
    return pres


def point_counts(grid, x, y):
    ix, iy, ok = grid.index(x, y)
    return np.bincount(iy[ok] * grid.nx + ix[ok], minlength=grid.nx * grid.ny).reshape(grid.ny, grid.nx), int((~ok).sum())


def distance_m(presence, size):
    from scipy.ndimage import distance_transform_edt

    if not presence.any():
        return np.full(presence.shape, np.nan)
    return distance_transform_edt(~presence) * size


def main():
    import duckdb
    import pyproj
    import shapely

    ap = argparse.ArgumentParser()
    ap.add_argument("features")
    ap.add_argument("geom_col")
    ap.add_argument("src_crs")
    ap.add_argument("grid")
    ap.add_argument("out")
    ap.add_argument("--where", default=None)
    ap.add_argument("--pad", type=int, default=50, help="margin in cells")
    ap.add_argument("--step", type=float, default=20.0)
    a = ap.parse_args()
    meta = json.load(open(a.grid))
    g = GridSpec(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    pg = padded(g, a.pad)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    col_type = {r[0]: r[1] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{a.features}')").fetchall()}[a.geom_col]
    expr = f'ST_AsWKB("{a.geom_col}")' if col_type.upper().startswith("GEOMETRY") else f'"{a.geom_col}"'
    where = f"WHERE {a.where}" if a.where else ""
    blobs = [bytes(r[0]) for r in con.execute(f"SELECT {expr} FROM read_parquet('{a.features}') {where}").fetchall() if r[0] is not None]
    geoms = shapely.from_wkb(blobs)
    tr = pyproj.Transformer.from_crs(a.src_crs, meta["crs"], always_xy=True)
    geoms = shapely.transform(geoms, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))
    kinds = shapely.get_type_id(geoms)
    is_point = kinds == 0
    pres = line_presence(pg, geoms[~is_point], a.step) if (~is_point).any() else np.zeros((pg.ny, pg.nx), bool)
    count = np.zeros((pg.ny, pg.nx), dtype=np.int64)
    off = 0
    if is_point.any():
        xy = shapely.get_coordinates(geoms[is_point])
        count, off = point_counts(pg, xy[:, 0], xy[:, 1])
        pres |= count > 0
    print(f"features read {len(blobs)} ({int(is_point.sum())} points, {int((~is_point).sum())} lines or polygons); "
          f"points off the padded grid {off}; marked cells in the grid {int(crop(pres, a.pad, g).sum())}")
    dist = crop(distance_m(pres, g.size), a.pad, g)
    np.savez_compressed(a.out, distance=dist.astype(np.float32), count=crop(count, a.pad, g).astype(np.int32))
    print(f"distance: median {np.nanmedian(dist):.0f} m, max {np.nanmax(dist):.0f} m; wrote {a.out}")


if __name__ == "__main__":
    main()

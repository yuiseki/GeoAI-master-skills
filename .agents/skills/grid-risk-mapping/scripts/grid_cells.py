"""A regular grid of square cells in a projected CRS, and the cell features that need the whole grid.

    Grid                  cell (ix, iy) covers x0 + ix*size <= x < x0 + (ix+1)*size, the same in y; row 0 is the south
                          edge; arrays are [iy, ix]
    cells_inside          the label of the polygon that holds each cell centre (-1 for none)
    box_sum, box_mean     the sum (outside the grid counts as 0) or the mean of the valid cells (NaN left out) over the
                          (2r + 1) x (2r + 1) square around each cell
    period_history        features from the periods before a target period only: each period's counts divided by that
                          period's total (so a period with ten times the events weighs the same), summed over squares,
                          for the last period and as the mean over all past periods; and the distance to the nearest
                          past event

Usage (build the cells of a set of polygons and write them):
    uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pyproj --with pandas --with pyarrow \\
        python grid_cells.py POLYGONS.parquet ID_COL GEOM_COL SRC_CRS DST_CRS SIZE_M OUT_DIR
"""

import json
import sys
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Grid:
    x0: float
    y0: float
    nx: int
    ny: int
    size: float = 100.0

    @classmethod
    def from_bounds(cls, minx, miny, maxx, maxy, size=100.0):
        x0 = np.floor(minx / size) * size
        y0 = np.floor(miny / size) * size
        # a bound exactly on a cell edge still gets its cell
        return cls(float(x0), float(y0), int(np.floor((maxx - x0) / size)) + 1, int(np.floor((maxy - y0) / size)) + 1, size)

    def index(self, x, y):
        ix = np.floor((np.asarray(x) - self.x0) / self.size).astype(np.int64)
        iy = np.floor((np.asarray(y) - self.y0) / self.size).astype(np.int64)
        return ix, iy, (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)

    def centres(self):
        return np.meshgrid(self.x0 + (np.arange(self.nx) + 0.5) * self.size, self.y0 + (np.arange(self.ny) + 0.5) * self.size)

    def sum_into(self, x, y, values=None):
        """[ny, nx] sums (or counts of points), and the total that fell off the grid."""
        ix, iy, ok = self.index(x, y)
        v = np.ones(len(ix)) if values is None else np.asarray(values, dtype=float)
        arr = np.bincount(iy[ok] * self.nx + ix[ok], weights=v[ok], minlength=self.nx * self.ny).reshape(self.ny, self.nx)
        return arr, float(v[~ok].sum())

    def to_dict(self):
        return {"x0": self.x0, "y0": self.y0, "nx": self.nx, "ny": self.ny, "size": self.size}


def cells_inside(grid, polygons):
    import shapely

    x, y = grid.centres()
    out = np.full(x.shape, -1, dtype=np.int32)
    for k, poly in enumerate(polygons):
        shapely.prepare(poly)
        out[shapely.contains_xy(poly, x, y) & (out == -1)] = k
    return out


def box_sum(a, r):
    if r == 0:
        return a.astype(float)
    c = np.pad(a.astype(float), ((r + 1, r), (r + 1, r))).cumsum(axis=0).cumsum(axis=1)
    k = 2 * r + 1
    return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]


def box_mean(a, r):
    ok = ~np.isnan(a)
    s = box_sum(np.where(ok, a, 0.0), r)
    n = box_sum(ok.astype(float), r)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / np.maximum(n, 1), np.nan)


def period_history(counts, target, radii, size):
    """counts: period -> [ny, nx]; radii: name -> radius in cells. Only the periods before `target` are read."""
    from scipy.ndimage import distance_transform_edt

    past = sorted(p for p in counts if p < target)
    if not past:
        raise ValueError(f"no period before {target}")
    share = {p: counts[p] / max(float(counts[p].sum()), 1.0) for p in past}
    f = {}
    for name, r in radii.items():
        f[f"h_last_{name}"] = box_sum(share[past[-1]], r)
        f[f"h_mean_{name}"] = sum(box_sum(share[p], r) for p in past) / len(past)
    any_past = sum(counts[p] for p in past) > 0
    f["h_dist"] = distance_transform_edt(~any_past) * size if any_past.any() else np.full(any_past.shape, np.nan)
    return f


def main():
    import duckdb
    import pandas as pd
    import pyproj
    import shapely

    src, id_col, geom_col, src_crs, dst_crs, size, out = sys.argv[1:8]
    size = float(size)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    rows = con.execute(f'SELECT "{id_col}", ST_AsWKB("{geom_col}") FROM read_parquet(\'{src}\') WHERE "{geom_col}" IS NOT NULL ORDER BY 1').fetchall()
    tr = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    def move(c):
        return np.column_stack(tr.transform(c[:, 0], c[:, 1]))

    polys = [shapely.transform(shapely.from_wkb(bytes(w)), move) for _, w in rows]
    g = Grid.from_bounds(*shapely.union_all(polys).bounds, size=size)
    lab = cells_inside(g, polys)
    n = int((lab >= 0).sum())
    area_poly = sum(p.area for p in polys)
    print(f"{len(polys)} polygons; grid {g.nx} x {g.ny}; cells inside {n} ({n * size ** 2 / 1e6:.1f} km2); polygon area {area_poly / 1e6:.1f} km2")
    iy, ix = np.nonzero(lab >= 0)
    back = pyproj.Transformer.from_crs(dst_crs, "EPSG:4326", always_xy=True)
    xc, yc = g.x0 + (ix + 0.5) * size, g.y0 + (iy + 0.5) * size
    lon, lat = back.transform(xc, yc)
    ids = np.array([r[0] for r in rows], dtype=object)
    pd.DataFrame({"cell": iy * g.nx + ix, "ix": ix, "iy": iy, "x": xc, "y": yc, "lon": lon, "lat": lat, "unit": ids[lab[iy, ix]]}).to_parquet(f"{out}/cells.parquet")
    np.savez_compressed(f"{out}/grid_mask.npz", label=lab)
    json.dump({**g.to_dict(), "crs": dst_crs, "ids": [str(i) for i in ids], "cells_inside": n}, open(f"{out}/grid.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

"""The 100 m analysis grid: square cells in a projected CRS (EPSG:6678, Japan Plane Rectangular CS X).

Cell (ix, iy) covers x0 + ix*size <= x < x0 + (ix+1)*size and the same in y. Row iy = 0 is the south edge.
Arrays are indexed [iy, ix].
"""

from dataclasses import dataclass

import numpy as np

CRS = "EPSG:6678"


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
        nx = int(np.floor((maxx - x0) / size)) + 1  # a bound exactly on a cell edge still gets its cell
        ny = int(np.floor((maxy - y0) / size)) + 1
        return cls(float(x0), float(y0), nx, ny, size)

    def index(self, x, y):
        """(ix, iy, inside): the cell of each point, and whether it is on the grid at all."""
        ix = np.floor((np.asarray(x) - self.x0) / self.size).astype(np.int64)
        iy = np.floor((np.asarray(y) - self.y0) / self.size).astype(np.int64)
        ok = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        return ix, iy, ok

    def centres(self):
        xs = self.x0 + (np.arange(self.nx) + 0.5) * self.size
        ys = self.y0 + (np.arange(self.ny) + 0.5) * self.size
        return np.meshgrid(xs, ys)

    def sum_into(self, x, y, values=None):
        """Sum values (or count points) into a [ny, nx] array; also return the total that fell off the grid."""
        ix, iy, ok = self.index(x, y)
        v = np.ones(len(ix)) if values is None else np.asarray(values, dtype=float)
        arr = np.bincount(iy[ok] * self.nx + ix[ok], weights=v[ok], minlength=self.nx * self.ny).reshape(self.ny, self.nx)
        return arr, float(v[~ok].sum())

    def to_dict(self, crs=CRS):
        return {"crs": crs, "x0": self.x0, "y0": self.y0, "nx": self.nx, "ny": self.ny, "size": self.size}


def load(art):
    """(Grid, crs) from ART_DIR/grid.json."""
    import json

    meta = json.load(open(f"{art}/grid.json"))
    return Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"]), meta.get("crs", CRS)


def lonlat_bbox(grid, crs, margin_deg=0.05):
    """(min lon, min lat, max lon, max lat) around the grid's corners, with a margin."""
    import pyproj

    tr = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    xs = [grid.x0, grid.x0 + grid.nx * grid.size]
    ys = [grid.y0, grid.y0 + grid.ny * grid.size]
    lon, lat = tr.transform([xs[0], xs[0], xs[1], xs[1]], [ys[0], ys[1], ys[0], ys[1]])
    return (min(lon) - margin_deg, min(lat) - margin_deg, max(lon) + margin_deg, max(lat) + margin_deg)


def worldcover_tiles(bbox):
    """Names of the 3 x 3 degree ESA WorldCover tiles (south-west corner) that a lon/lat bbox touches."""
    import math

    lons = range(int(math.floor(bbox[0] / 3) * 3), int(math.floor(bbox[2] / 3) * 3) + 1, 3)
    lats = range(int(math.floor(bbox[1] / 3) * 3), int(math.floor(bbox[3] / 3) * 3) + 1, 3)
    return [f"N{la:02d}E{lo:03d}" for la in lats for lo in lons]

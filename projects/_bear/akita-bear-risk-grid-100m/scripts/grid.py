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

    def to_dict(self):
        return {"crs": CRS, "x0": self.x0, "y0": self.y0, "nx": self.nx, "ny": self.ny, "size": self.size}

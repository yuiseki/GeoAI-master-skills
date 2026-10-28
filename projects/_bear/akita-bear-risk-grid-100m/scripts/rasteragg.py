"""Put raster pixels into the 100 m grid cells by the centre of each pixel, keeping the kind of value apart.

    ClassAcc  land cover classes: pixel counts per class and cell; fractions are over the valid pixels
    SumAcc    quantities (people): sums per cell; the total off the grid is kept, so the total can be checked
    MeanAcc   levels (elevation): mean over the valid pixels; a cell with no valid pixel is NaN, not 0

NoData pixels and pixels whose centre is off the grid are counted, never read as 0.
"""

import numpy as np


def pixel_centres(transform, row0, nrows, col0, ncols):
    """Longitude and latitude (or x and y) of the pixel centres of a block, for a north-up affine transform."""
    cols = col0 + np.arange(ncols) + 0.5
    rows = row0 + np.arange(nrows) + 0.5
    if transform.b != 0 or transform.d != 0:
        raise ValueError("rotated rasters are not handled")
    xs = transform.c + cols * transform.a
    ys = transform.f + rows * transform.e
    return np.meshgrid(xs, ys)


class _Acc:
    def __init__(self, grid):
        self.grid = grid
        self.nodata = np.zeros((grid.ny, grid.nx), dtype=np.int64)
        self.outside = 0.0

    def _split(self, values, x, y, nodata):
        v = np.asarray(values).ravel()
        ix, iy, ok = self.grid.index(np.asarray(x).ravel(), np.asarray(y).ravel())
        bad = np.isnan(v) if nodata is None else (v == nodata)
        if np.issubdtype(v.dtype, np.floating):
            bad |= np.isnan(v)
        flat = iy * self.grid.nx + ix
        n = self.grid.nx * self.grid.ny
        self.nodata += np.bincount(flat[ok & bad], minlength=n).reshape(self.nodata.shape)
        return v, flat, ok & ~bad, ~ok & ~bad


class ClassAcc(_Acc):
    def __init__(self, grid, classes):
        super().__init__(grid)
        self.counts = {c: np.zeros((grid.ny, grid.nx), dtype=np.int64) for c in classes}
        self.other = np.zeros((grid.ny, grid.nx), dtype=np.int64)

    def add(self, values, x, y, nodata):
        v, flat, good, off = self._split(values, x, y, nodata)
        self.outside += float(off.sum())
        n = self.grid.nx * self.grid.ny
        known = np.zeros(len(v), dtype=bool)
        for c, arr in self.counts.items():
            sel = good & (v == c)
            known |= sel
            arr += np.bincount(flat[sel], minlength=n).reshape(arr.shape)
        self.other += np.bincount(flat[good & ~known], minlength=n).reshape(self.other.shape)

    def valid(self):
        return sum(self.counts.values()) + self.other

    def fractions(self):
        val = self.valid()
        with np.errstate(invalid="ignore", divide="ignore"):
            return {c: np.where(val > 0, a / val, np.nan) for c, a in self.counts.items()}


class SumAcc(_Acc):
    def __init__(self, grid):
        super().__init__(grid)
        self.total = np.zeros((grid.ny, grid.nx))

    def add(self, values, x, y, nodata):
        v, flat, good, off = self._split(values, x, y, nodata)
        self.outside += float(v[off].sum())
        self.total += np.bincount(flat[good], weights=v[good], minlength=self.grid.nx * self.grid.ny).reshape(self.total.shape)


class MeanAcc(_Acc):
    def __init__(self, grid):
        super().__init__(grid)
        self.s = np.zeros((grid.ny, grid.nx))
        self.n = np.zeros((grid.ny, grid.nx), dtype=np.int64)

    def add(self, values, x, y, nodata):
        v, flat, good, off = self._split(values, x, y, nodata)
        self.outside += float(off.sum())
        size = self.grid.nx * self.grid.ny
        self.s += np.bincount(flat[good], weights=v[good], minlength=size).reshape(self.s.shape)
        self.n += np.bincount(flat[good], minlength=size).reshape(self.n.shape)

    def mean(self):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(self.n > 0, self.s / np.maximum(self.n, 1), np.nan)

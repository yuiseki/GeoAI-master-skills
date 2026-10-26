"""Put the pixels of a raster into the cells of a regular square grid by the centre of each pixel.

For a grid of many small cells (a million 100 m cells), measuring each cell as a polygon is slow; this moves each
pixel centre into the grid's CRS and counts it in the cell it falls in. The raster is never resampled. The value's
kind decides what a cell gets:

    class   pixel counts per class; the output holds the fraction of each class over the cell's valid pixels
    sum     a quantity (people, counts): the sum of the pixels; the total off the grid is printed, so it can be checked
    mean    a level (elevation): the mean over the valid pixels; a cell with no valid pixel is NaN, not 0

NoData pixels are counted per cell and never read as 0. When the pixel is near the size of the cell, a cell holds
one or two pixel centres and single-cell values come out blocky: use sums or means over a neighbourhood.

Usage:
    uvx --with rasterio --with numpy --with pyproj python raster_to_grid.py RASTER GRID.json --kind class|sum|mean \\
        --out OUT.npz [--classes 10 20 30] [--bbox MINX MINY MAXX MAXY] [--mask MASK.npz --mask-key label]

GRID.json holds x0, y0, nx, ny, size (the south-west corner, the number of cells, the cell size in the CRS unit) and
crs. --bbox is in the raster's CRS and limits the window read. Rows of the raster are read in blocks.
Unset anaconda's GDAL_DATA, GDAL_DRIVER_PATH, PROJ_DATA before running if they point at another GDAL.
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


def pixel_centres(transform, row0, nrows, col0, ncols):
    """x and y of the pixel centres of a block, for a north-up affine transform."""
    if transform.b != 0 or transform.d != 0:
        raise ValueError("rotated rasters are not handled")
    xs = transform.c + (col0 + np.arange(ncols) + 0.5) * transform.a
    ys = transform.f + (row0 + np.arange(nrows) + 0.5) * transform.e
    return np.meshgrid(xs, ys)


class _Acc:
    def __init__(self, grid):
        self.grid = grid
        self.nodata = np.zeros((grid.ny, grid.nx), dtype=np.int64)
        self.pixels = np.zeros((grid.ny, grid.nx), dtype=np.int64)
        self.off_grid = 0

    def _split(self, values, x, y, nodata):
        v = np.asarray(values).ravel()
        ix, iy, ok = self.grid.index(np.asarray(x).ravel(), np.asarray(y).ravel())
        bad = np.zeros(len(v), dtype=bool) if nodata is None else (v == nodata)
        if np.issubdtype(v.dtype, np.floating):
            bad |= np.isnan(v)
        flat = iy * self.grid.nx + ix
        n = self.grid.nx * self.grid.ny
        self.nodata += np.bincount(flat[ok & bad], minlength=n).reshape(self.nodata.shape)
        self.pixels += np.bincount(flat[ok], minlength=n).reshape(self.pixels.shape)
        self.off_grid += int((~ok).sum())
        return v, flat, ok & ~bad, ~ok & ~bad


class ClassAcc(_Acc):
    def __init__(self, grid, classes):
        super().__init__(grid)
        self.counts = {c: np.zeros((grid.ny, grid.nx), dtype=np.int64) for c in classes}
        self.other = np.zeros((grid.ny, grid.nx), dtype=np.int64)

    def add(self, values, x, y, nodata):
        v, flat, good, _ = self._split(values, x, y, nodata)
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
        self.off_grid_total = 0.0

    def add(self, values, x, y, nodata):
        v, flat, good, off = self._split(values, x, y, nodata)
        self.off_grid_total += float(v[off].sum())
        self.total += np.bincount(flat[good], weights=v[good], minlength=self.grid.nx * self.grid.ny).reshape(self.total.shape)


class MeanAcc(_Acc):
    def __init__(self, grid):
        super().__init__(grid)
        self.s = np.zeros((grid.ny, grid.nx))
        self.n = np.zeros((grid.ny, grid.nx), dtype=np.int64)

    def add(self, values, x, y, nodata):
        v, flat, good, _ = self._split(values, x, y, nodata)
        size = self.grid.nx * self.grid.ny
        self.s += np.bincount(flat[good], weights=v[good], minlength=size).reshape(self.s.shape)
        self.n += np.bincount(flat[good], minlength=size).reshape(self.n.shape)

    def mean(self):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(self.n > 0, self.s / np.maximum(self.n, 1), np.nan)


def main():
    import pyproj
    import rasterio
    from rasterio.windows import Window, from_bounds

    ap = argparse.ArgumentParser()
    ap.add_argument("raster")
    ap.add_argument("grid")
    ap.add_argument("--kind", choices=["class", "sum", "mean"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--classes", type=int, nargs="*", default=[])
    ap.add_argument("--bbox", type=float, nargs=4, default=None)
    ap.add_argument("--mask", default=None, help="npz with the grid's cells of interest (>= 0), for the printed counts")
    ap.add_argument("--mask-key", default="label")
    ap.add_argument("--rows", type=int, default=512)
    a = ap.parse_args()
    if a.kind == "class" and not a.classes:
        raise SystemExit("--kind class needs --classes")
    meta = json.load(open(a.grid))
    g = GridSpec(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    acc = {"class": lambda: ClassAcc(g, a.classes), "sum": lambda: SumAcc(g), "mean": lambda: MeanAcc(g)}[a.kind]()
    window_total = 0.0
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(a.raster) as src:
            tr = pyproj.Transformer.from_crs(src.crs, meta["crs"], always_xy=True)
            win = Window(0, 0, src.width, src.height)
            if a.bbox:
                win = from_bounds(*a.bbox, transform=src.transform).round_offsets().round_lengths().intersection(win)
            r0, c0, nr, nc = int(win.row_off), int(win.col_off), int(win.height), int(win.width)
            print(f"raster {src.crs}, pixel {src.res}, nodata {src.nodata}; window rows {r0}..{r0 + nr}, cols {c0}..{c0 + nc}")
            for rr in range(r0, r0 + nr, a.rows):
                h = min(a.rows, r0 + nr - rr)
                vals = src.read(1, window=Window(c0, rr, nc, h))
                if a.kind == "sum":
                    ok = ~np.isnan(vals) if src.nodata is None else (vals != src.nodata) & ~np.isnan(vals)
                    window_total += float(vals[ok].sum())
                x, y = pixel_centres(src.transform, rr, h, c0, nc)
                px, py = tr.transform(x.ravel(), y.ravel())
                acc.add(vals.ravel(), px, py, nodata=src.nodata)
    cells = np.ones((g.ny, g.nx), dtype=bool) if a.mask is None else np.load(a.mask)[a.mask_key] >= 0
    pix = acc.pixels[cells]
    print(f"pixel centres per cell of interest: min {pix.min()}, median {np.median(pix):.0f}, max {pix.max()}; "
          f"cells without a pixel {int((pix == 0).sum())}; NoData pixels in them {int(acc.nodata[cells].sum())}; "
          f"pixels off the grid {acc.off_grid}")
    out = {"pixels": acc.pixels.astype(np.int32), "nodata": acc.nodata.astype(np.int32)}
    if a.kind == "class":
        out.update({f"f{c}": v.astype(np.float32) for c, v in acc.fractions().items()})
        out["valid"] = acc.valid().astype(np.int32)
    elif a.kind == "sum":
        out["total"] = acc.total
        on = acc.total.sum()
        print(f"window total {window_total:.6g} = on the grid {on:.6g} + off the grid {acc.off_grid_total:.6g}; "
              f"cells of interest {acc.total[cells].sum():.6g}")
        if not np.isclose(window_total, on + acc.off_grid_total, rtol=1e-9, atol=1e-6):
            raise SystemExit("the total is not kept")
    else:
        out["mean"] = acc.mean().astype(np.float32)
        out["n"] = acc.n.astype(np.int32)
    np.savez_compressed(a.out, **out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()

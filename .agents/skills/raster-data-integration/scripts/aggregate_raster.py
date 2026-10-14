"""Aggregate one raster band to analysis units (polygons), keeping NoData, outside-the-raster and valid apart.

The kind of quantity decides the statistic, and must be given; there is no default.
    extensive    a count or amount per pixel (population): sum
    intensive    a level that does not grow with area (elevation, temperature): area-weighted mean, min, max
    categorical  a class code (land cover): area share of each class, and the majority class

Pixels are given to a unit by one of four rules:
    centre       a pixel belongs to the unit if its centre is inside (rasterio's default). A unit smaller
                 than a pixel can hold no centre; it is reported as no_pixel_centre, not as 0.
    fraction     each pixel is weighted by the share of its area inside, measured on a grid --subdivide
                 times finer in each direction (10 gives the share to 1 %).
    exact        each pixel is weighted by the area of its intersection with the polygon, divided by the
                 pixel's area (in the raster's CRS, so the share, not the area, is what is exact).
    all_touched  every pixel the polygon touches counts whole. It always over-counts; it is here to measure
                 that, not to sum quantities.

Units are moved onto the raster's CRS (the raster is never resampled here). Pixel areas are measured on the
ellipsoid for a geographic raster, so degrees are never used as area. Scale and offset in the file are applied
to the values before aggregating.

A unit may also be a point: it takes the value of the pixel it falls in (a point on a pixel edge goes to the
pixel east or south of it). Lines are refused.

Every unit gets a row: status is ok, no_valid_pixels (all NoData), outside_raster, no_pixel_centre,
empty_geometry or unsupported_geometry. Columns cells_valid, cells_nodata, cells_outside are pixel counts (weighted by the share
inside under fraction), area_*_km2 the same in km2, unit_area_km2 the polygon's own area on the ellipsoid.

For an extensive raster the total is checked: the raster's sum over the union of all units against the sum
of the units. Overlapping units count the same pixels twice; a unit that went missing loses them. The
difference is printed, and the run exits with status 2 if it is larger than --tolerance (relative).

Usage:
    uvx --from 'duckdb>=1.5.5' --with rasterio --with shapely --with pyproj --with pyarrow \\
        python aggregate_raster.py RASTER UNITS UNIT_ID --kind extensive|intensive|categorical \\
        --units-crs EPSG:4612 [--geom geometry] [--method centre|fraction|exact|all_touched] [--subdivide 10] \\
        [--band 1] [--tolerance 0.001] [--max-pixels 200000000] --out units_raster.parquet
"""

import argparse
import math
import sys

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyproj
import rasterio
import shapely
from rasterio.features import rasterize
from rasterio.transform import Affine

KINDS = ("extensive", "intensive", "categorical")


def read_units(path, unit_id, geom):
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    typ = {r[0]: r[1] for r in con.sql(f"describe select * from '{path}'").fetchall()}[geom]
    expr = {"GEOMETRY": f"ST_AsWKB(\"{geom}\")", "VARCHAR": f"ST_AsWKB(ST_GeomFromText(\"{geom}\"))"}.get(
        typ.split("(")[0], f"\"{geom}\"")
    rows = con.sql(f"select \"{unit_id}\", {expr} from '{path}'").fetchall()
    ids = [r[0] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{unit_id} is not unique: {len(ids) - len(set(ids))} duplicate ids")
    return ids, [shapely.from_wkb(bytes(r[1])) if r[1] is not None else None for r in rows]


def to_crs(geoms, src, dst):
    if pyproj.CRS(src) == pyproj.CRS(dst):
        return geoms
    tr = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    return [None if g is None else shapely.transform(g, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))
            for g in geoms]


class Grid:
    """Pixel geometry of the raster: windows, cell areas in km2, and the inside-the-raster mask."""

    def __init__(self, ds):
        t = ds.transform
        if t.b or t.d or t.e >= 0:
            raise SystemExit("only north-up rasters without rotation are handled")
        self.t, self.h, self.w = t, ds.height, ds.width
        self.geographic = ds.crs.is_geographic
        self.geod = pyproj.Geod(ellps="WGS84")
        self.unit = 1.0 if self.geographic else ds.crs.linear_units_factor[1]
        self._rows = {}

    def window(self, bounds):
        minx, miny, maxx, maxy = bounds
        c0 = math.floor((minx - self.t.c) / self.t.a)
        c1 = math.ceil((maxx - self.t.c) / self.t.a)
        r0 = math.floor((maxy - self.t.f) / self.t.e)
        r1 = math.ceil((miny - self.t.f) / self.t.e)
        return r0, max(r1, r0 + 1), c0, max(c1, c0 + 1)

    def row_area_km2(self, r):
        if r not in self._rows:
            if self.geographic:
                top = self.t.f + r * self.t.e
                lats = [top, top, top + self.t.e, top + self.t.e]
                lons = [0, self.t.a, self.t.a, 0]
                self._rows[r] = abs(self.geod.polygon_area_perimeter(lons, lats)[0]) / 1e6
            else:
                self._rows[r] = abs(self.t.a * self.t.e) * self.unit**2 / 1e6
        return self._rows[r]

    def areas(self, r0, r1, c0, c1):
        return np.repeat(np.array([self.row_area_km2(r) for r in range(r0, r1)])[:, None], c1 - c0, axis=1)

    def weights(self, geom, r0, r1, c0, c1, method, k):
        h, w = r1 - r0, c1 - c0
        t = self.t @ Affine.translation(c0, r0)
        if method in ("centre", "all_touched"):
            return rasterize([(geom, 1)], out_shape=(h, w), transform=t, dtype="uint8",
                             all_touched=method == "all_touched").astype("float64")
        if method == "exact":
            xs = self.t.c + self.t.a * np.arange(c0, c1 + 1)
            ys = self.t.f + self.t.e * np.arange(r0, r1 + 1)
            boxes = shapely.box(xs[None, :-1], ys[1:, None], xs[None, 1:], ys[:-1, None])
            shapely.prepare(geom)
            return shapely.area(shapely.intersection(boxes, geom)) / abs(self.t.a * self.t.e)
        fine = rasterize([(geom, 1)], out_shape=(h * k, w * k), transform=t @ Affine.scale(1 / k), dtype="uint8")
        return fine.reshape(h, k, w, k).sum(axis=(1, 3)) / (k * k)

    def inside(self, r0, r1, c0, c1):
        rr = np.arange(r0, r1)[:, None]
        cc = np.arange(c0, c1)[None, :]
        return (rr >= 0) & (rr < self.h) & (cc >= 0) & (cc < self.w)


def read_values(ds, band, r0, r1, c0, c1):
    """Values (scale and offset applied) and the valid mask over a window that may reach past the raster."""
    h, w = r1 - r0, c1 - c0
    vals = np.zeros((h, w), dtype="float64")
    valid = np.zeros((h, w), dtype=bool)
    rr0, rr1, cc0, cc1 = max(r0, 0), min(r1, ds.height), max(c0, 0), min(c1, ds.width)
    if rr0 < rr1 and cc0 < cc1:
        win = rasterio.windows.Window(cc0, rr0, cc1 - cc0, rr1 - rr0)
        raw = ds.read(band, window=win)
        ok = np.ones(raw.shape, dtype=bool)
        if ds.nodatavals[band - 1] is not None:
            ok &= raw != ds.nodatavals[band - 1]
        if np.issubdtype(raw.dtype, np.floating):
            ok &= ~np.isnan(raw)
        v = raw.astype("float64") * ds.scales[band - 1] + ds.offsets[band - 1]
        sl = (slice(rr0 - r0, rr1 - r0), slice(cc0 - c0, cc1 - c0))
        vals[sl], valid[sl] = v, ok
    return vals, valid


def aggregate(raster, units, unit_id, kind, out, units_crs, geom="geometry", method="centre", subdivide=10,
              band=1, tolerance=0.001, max_pixels=200_000_000):
    if kind not in KINDS:
        raise SystemExit(f"--kind must be one of {KINDS}")
    ids, geoms = read_units(units, unit_id, geom)
    with rasterio.open(raster) as ds:
        if ds.nodatavals[band - 1] is None:
            print("warning: the raster declares no NoData value; every pixel is taken as valid", file=sys.stderr)
        if ds.scales[band - 1] != 1 or ds.offsets[band - 1] != 0:
            print(f"scale {ds.scales[band - 1]} and offset {ds.offsets[band - 1]} applied to the values")
        grid = Grid(ds)
        on_raster = to_crs(geoms, units_crs, ds.crs.to_wkt())
        lonlat = to_crs(geoms, units_crs, "EPSG:4326")
        rows, classes = [], set()
        for uid, g, ll in zip(ids, on_raster, lonlat):
            row = {"id": uid, "unit_area_km2": None}
            if g is None or g.is_empty:
                rows.append({**row, "status": "empty_geometry"})
                continue
            if g.geom_type == "Point":
                # the pixel the point falls in; a point on a pixel edge goes to the pixel east or south of it
                r0 = math.floor((g.y - grid.t.f) / grid.t.e)
                c0 = math.floor((g.x - grid.t.c) / grid.t.a)
                r1, c1 = r0 + 1, c0 + 1
                wt = np.ones((1, 1))
                row["unit_area_km2"] = 0.0
            elif g.geom_type in ("Polygon", "MultiPolygon"):
                row["unit_area_km2"] = abs(grid.geod.geometry_area_perimeter(ll)[0]) / 1e6
                r0, r1, c0, c1 = grid.window(g.bounds)
                wt = grid.weights(g, r0, r1, c0, c1, method, subdivide)
            else:
                rows.append({**row, "status": "unsupported_geometry"})
                continue
            ins = grid.inside(r0, r1, c0, c1)
            vals, valid = read_values(ds, band, r0, r1, c0, c1)
            area = grid.areas(r0, r1, c0, c1)
            use = (wt > 0) & valid
            row.update(
                cells_valid=float(wt[use].sum()), cells_nodata=float(wt[(wt > 0) & ins & ~valid].sum()),
                cells_outside=float(wt[(wt > 0) & ~ins].sum()),
                area_valid_km2=float((wt * area)[use].sum()), area_nodata_km2=float((wt * area)[(wt > 0) & ins & ~valid].sum()),
                area_outside_km2=float((wt * area)[(wt > 0) & ~ins].sum()))
            if not ins.any() or ((wt > 0).any() and not ((wt > 0) & ins).any()):
                row["status"] = "outside_raster"
            elif not (wt > 0).any():
                row["status"] = "no_pixel_centre"
            elif not use.any():
                row["status"] = "no_valid_pixels"
            else:
                row["status"] = "ok"
                if kind == "extensive":
                    row["sum"] = float((wt * vals)[use].sum())
                elif kind == "intensive":
                    aw = (wt * area)[use]
                    row["mean"] = float((aw * vals[use]).sum() / aw.sum())
                    row["min"], row["max"] = float(vals[use].min()), float(vals[use].max())
                else:
                    aw = (wt * area)[use]
                    cl = vals[use].round().astype("int64")
                    share = {int(c): float(aw[cl == c].sum() / aw.sum()) for c in np.unique(cl)}
                    classes |= set(share)
                    row["share"] = share
            rows.append(row)

        report = check_total(ds, band, grid, on_raster, method, subdivide, max_pixels) if kind == "extensive" else {}

    write(rows, kind, sorted(classes), out)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"units: {len(rows)}  " + "  ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    if len(rows) != len(ids):
        raise SystemExit(f"wrote {len(rows)} of {len(ids)} units")
    if report:
        report["assigned_total"] = sum(r.get("sum") or 0.0 for r in rows)
        diff = report["assigned_total"] - report["raster_total_in_units"]
        report["relative_difference"] = diff / report["raster_total_in_units"] if report["raster_total_in_units"] else float("nan")
        report["ok"] = abs(report["relative_difference"]) <= tolerance
        for k, v in report.items():
            print(f"{k}: {v}")
    return report


def check_total(ds, band, grid, geoms, method, k, max_pixels):
    """Raster sum over the union of the units, and how much of it the units count more than once."""
    present = [g for g in geoms if g is not None and not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon")]
    if not present:
        return {}
    union = shapely.union_all(present)
    r0, r1, c0, c1 = grid.window(union.bounds)
    if (r1 - r0) * (c1 - c0) > max_pixels:
        print(f"total not checked: the units span {(r1 - r0) * (c1 - c0)} pixels (> --max-pixels)", file=sys.stderr)
        return {}
    vals, valid = read_values(ds, band, r0, r1, c0, c1)
    u = grid.weights(union, r0, r1, c0, c1, method, k)
    total_w = np.zeros_like(u)
    for g in present:
        a0, a1, b0, b1 = grid.window(g.bounds)
        w = grid.weights(g, a0, a1, b0, b1, method, k)
        total_w[a0 - r0:a1 - r0, b0 - c0:b1 - c0] += w
    v = np.where(valid, vals, 0.0)
    return {"raster_total_in_units": float((u * v).sum()),
            "counted_twice": float((np.clip(total_w - u, 0, None) * v).sum()),
            "nodata_area_in_units_km2": float((u * grid.areas(r0, r1, c0, c1))[~valid & grid.inside(r0, r1, c0, c1)].sum())}


def write(rows, kind, classes, out):
    stat = {"extensive": ["sum"], "intensive": ["mean", "min", "max"], "categorical": []}[kind]
    cols = {"id": [r["id"] for r in rows], "status": [r["status"] for r in rows]}
    for c in stat:
        cols[c] = [r.get(c) for r in rows]
    if kind == "categorical":
        for c in classes:
            cols[f"class_{c}"] = [r["share"].get(c, 0.0) if "share" in r else None for r in rows]
        cols["majority"] = [min(r["share"], key=lambda c: (-r["share"][c], c)) if "share" in r else None for r in rows]
    for c in ("cells_valid", "cells_nodata", "cells_outside", "area_valid_km2", "area_nodata_km2",
              "area_outside_km2", "unit_area_km2"):
        cols[c] = [r.get(c) for r in rows]
    pq.write_table(pa.table(cols), out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("raster")
    p.add_argument("units")
    p.add_argument("unit_id")
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--units-crs", required=True, help="CRS of the units' coordinates, such as EPSG:4612")
    p.add_argument("--geom", default="geometry")
    p.add_argument("--method", default="centre", choices=("centre", "fraction", "exact", "all_touched"))
    p.add_argument("--subdivide", type=int, default=10)
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--tolerance", type=float, default=0.001)
    p.add_argument("--max-pixels", type=int, default=200_000_000)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    report = aggregate(a.raster, a.units, a.unit_id, a.kind, a.out, a.units_crs, a.geom, a.method, a.subdivide,
                       a.band, a.tolerance, a.max_pixels)
    if report and not report["ok"]:
        print("total not conserved: see relative_difference and counted_twice above", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

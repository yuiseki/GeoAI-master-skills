"""Flow directions, upstream area, catchments of pour points, a stream network and HAND from a DEM.

Depressions are filled (priority flood, Wang and Liu 2006, as implemented in pyflwdir) and D8 flow directions are
taken on the filled surface, so every valid cell drains to the edge of the valid data. Upstream area is the area of
all cells whose flow path passes through a cell, the cell itself included.

Pour points (dams, gauges, outlets) are moved to a stream cell before their catchments are taken: among the cells
within --snap-m whose upstream area is at least --snap-min-km2, the nearest one (ties: the larger upstream area).
Taking the cell of largest upstream area within the radius instead would jump downstream of a dam or a confluence
and add the area below it; that rule is not offered. A point with no such cell is reported as not snapped and gets
no catchment, rather than a catchment from where it lies.

Closed basins (a lake with no surface outlet) are filled over and spill into a neighbour unless they are given as
--sinks: then their depressions drain to them, and the area they drain is printed.

Each pour point gets its whole catchment (nested points each get their own, overlapping ones). A catchment that
reaches the edge of the raster or of the valid data may be cut by it and is flagged.

The grid must be in a projected CRS in metres, without rotation, whose areal scale over the raster stays within
--max-scale-error of 1 (Web Mercator at 35 degrees north overstates areas by about 50% and is stopped). A raster
without a CRS stops: give it the one from its metadata first.

Output: one GeoTIFF with float32 bands, NoData NaN:
    1 upstream area (km2)
    2 D8 flow direction (pyflwdir's d8 codes: 1 E, 2 SE, 4 S, 8 SW, 16 W, 32 NW, 64 N, 128 NE, 0 pit/outlet)
    3 stream (1 where upstream area >= --stream-km2, else 0); NaN when --stream-km2 is not given
    4 HAND (m above the stream cell the flow path first reaches, on the filled DEM); NaN without --stream-km2
    5 filled DEM (m)
and, with --points, OUT.points.csv: id, x, y, row, col, snapped, snap_m, upstream_km2, catchment_km2,
catchment_cells, edge_cells (catchment cells on the raster edge or next to NoData; > 0 means it may be cut).

Usage:
    uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj python hydro.py DEM.tif --out OUT.tif \\
        [--points POINTS.csv --id id --x x --y y --points-crs EPSG:4326 --snap-m 300 --snap-min-km2 1] \\
        [--sinks SINKS.csv] [--stream-km2 1] [--max-scale-error 0.02]
"""

import argparse
import csv
import math
import sys

import numpy as np
import rasterio

NODATA = -9999.0


def grid_checks(crs, transform, shape, max_scale_error):
    """Stop unless the grid is projected, in metres, not rotated, with areal scale near 1. Returns the largest
    departure of the areal scale from 1 over nine points of the raster."""
    from pyproj import CRS, Proj, Transformer

    if crs is None:
        sys.exit("the DEM has no CRS. Set it from the source's metadata (for a STAC item, proj:epsg) and rerun")
    c = CRS.from_user_input(crs)
    if c.is_geographic:
        sys.exit(f"the DEM is in a geographic CRS ({c.name}); reproject it to a local projected CRS in metres "
                 "(a UTM zone, a national plane rectangular system)")
    unit = c.axis_info[0].unit_name if c.axis_info else ""
    factor = c.axis_info[0].unit_conversion_factor if c.axis_info else float("nan")
    if not math.isclose(factor, 1.0):
        sys.exit(f"the DEM's CRS unit is {unit} (factor {factor}); reproject to metres")
    if transform.b != 0 or transform.d != 0:
        sys.exit("the DEM's grid is rotated; resample it to a north-up grid")
    h, w = shape
    to_ll = Transformer.from_crs(c, c.geodetic_crs, always_xy=True)
    proj = Proj(c)
    worst = 0.0
    for r in (0.5, h / 2, h - 0.5):
        for col in (0.5, w / 2, w - 0.5):
            x, y = transform * (col, r)
            lon, lat = to_ll.transform(x, y)
            worst = max(worst, abs(proj.get_factors(lon, lat).areal_scale - 1))
    if worst > max_scale_error:
        sys.exit(f"the CRS's areal scale departs from 1 by up to {worst:.3f} over the DEM (limit {max_scale_error}); "
                 "areas would be off by that much. Reproject to a local projected CRS")
    return worst


D8_CODES = {(0, 1): 1, (1, 1): 2, (1, 0): 4, (1, -1): 8, (0, -1): 16, (-1, -1): 32, (-1, 0): 64, (-1, 1): 128}


def steepest_d8(filled, valid, d8_flood, dx, dy):
    """D8 by steepest descent (drop divided by the distance between centres) on the filled DEM. Cells with no
    strictly lower valid neighbour (flats left by the filling, outlets) keep the direction from the priority flood,
    which leads across the flat towards its outlet. Strictly downhill steps cannot return to a cell, and the flood's
    steps on a flat follow the order in which the flood reached it, so no loop is made."""
    h, w = filled.shape
    big = np.pad(np.where(valid, filled, np.inf), 1, constant_values=np.inf)
    best = np.zeros((h, w))
    code = np.zeros((h, w), dtype=np.uint8)
    diag = math.hypot(dx, dy)
    for (dr, dc), cd in D8_CODES.items():
        nb = big[1 + dr:1 + dr + h, 1 + dc:1 + dc + w]
        dist = diag if dr and dc else (dx if dc else dy)
        with np.errstate(invalid="ignore"):
            s = (filled - nb) / dist
        take = np.isfinite(s) & (s > best)
        best = np.where(take, s, best)
        code = np.where(take, cd, code)
    return np.where(valid & (best > 0), code, d8_flood).astype(np.uint8)


def flow(z, transform, nodata=NODATA, rule="steepest", sinks=None):
    """Fill depressions, then take D8 directions on the filled DEM. rule="steepest" is the steepest descent with the
    distance to diagonal neighbours (O'Callaghan and Mark 1984); rule="flood" keeps pyflwdir's own directions, which
    go to the lowest neighbour without dividing the drop by the distance.

    sinks: flat indices of cells where water leaves the surface (closed basins: lakes without a surface outlet,
    swallow holes). They are not filled over, and their depressions drain to them. The edge of the valid data stays
    an outlet too: pyflwdir drops the edge when given its own pits, so the edge cells are passed with them.
    Returns (filled DEM, d8, FlwdirRaster)."""
    import pyflwdir
    from pyflwdir import dem

    valid = z != nodata
    if sinks is None or len(sinks) == 0:
        filled, d8 = dem.fill_depressions(z.astype("float64"), nodata=nodata)
    else:
        pits = np.union1d(np.flatnonzero(edge_mask(valid)), np.asarray(sinks, dtype=np.int64))
        filled, d8 = dem.fill_depressions(z.astype("float64"), nodata=nodata, idxs_pit=pits)
    if rule == "steepest":
        d8 = steepest_d8(filled, valid, d8, abs(transform.a), abs(transform.e))
    elif rule != "flood":
        raise ValueError(f"unknown rule {rule}")
    if sinks is not None and len(sinks):
        d8.flat[np.asarray(sinks, dtype=np.int64)] = 0
    fd = pyflwdir.from_array(d8, ftype="d8", transform=transform, latlon=False)
    return filled, d8, fd


def snap(upa, row, col, radius_cells, min_area):
    """The nearest cell within radius_cells (Euclidean, in cells) whose upstream area is at least min_area; ties go to
    the larger upstream area. Returns (row, col, distance in cells) or None."""
    h, w = upa.shape
    best = None
    rad = int(math.floor(radius_cells))
    for dr in range(-rad, rad + 1):
        for dc in range(-rad, rad + 1):
            r, c = row + dr, col + dc
            d = math.hypot(dr, dc)
            if d > radius_cells or not (0 <= r < h and 0 <= c < w):
                continue
            a = upa[r, c]
            if not np.isfinite(a) or a < min_area:
                continue
            key = (d, -a)
            if best is None or key < best[0]:
                best = (key, r, c, d)
    return None if best is None else (best[1], best[2], best[3])


def edge_mask(valid):
    """Valid cells on the raster edge or with a NoData cell among their 8 neighbours."""
    pad = np.pad(valid, 1, constant_values=False)
    allnb = np.ones_like(valid)
    h, w = valid.shape
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            allnb &= pad[1 + dr:1 + dr + h, 1 + dc:1 + dc + w]
    return valid & ~allnb


def read_points(path, id_col, x_col, y_col):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path} has no rows")
    for k in (id_col, x_col, y_col):
        if k not in rows[0]:
            sys.exit(f"{path} has no column {k}")
    ids = [r[id_col] for r in rows]
    if len(set(ids)) != len(ids):
        sys.exit(f"{path}: ids are not unique")
    return ids, np.array([float(r[x_col]) for r in rows]), np.array([float(r[y_col]) for r in rows])


def to_cells(transform, crs, shape, xs, ys, from_crs=None):
    """Rows and columns of points; None for a point outside the raster."""
    if from_crs:
        from pyproj import Transformer
        xs, ys = Transformer.from_crs(from_crs, crs, always_xy=True).transform(xs, ys)
    out = []
    for x, y in zip(xs, ys):
        r, c = rasterio.transform.rowcol(transform, x, y)
        out.append((r, c) if 0 <= r < shape[0] and 0 <= c < shape[1] else None)
    return np.asarray(xs), np.asarray(ys), out


def run(dem_path, out_path, points=None, id_col="id", x_col="x", y_col="y", points_crs=None, snap_m=300.0,
        snap_min_km2=1.0, stream_km2=None, max_scale_error=0.02, sinks=None):
    with rasterio.open(dem_path) as src:
        z = src.read(1).astype("float64")
        transform, crs, nd = src.transform, src.crs, src.nodata
    worst = grid_checks(crs, transform, z.shape, max_scale_error)
    valid = np.isfinite(z) & ((z != nd) if nd is not None else True)
    z = np.where(valid, z, NODATA)
    n_cells, n_valid = z.size, int(valid.sum())
    print(f"cells {n_cells}: valid {n_valid}, NoData {n_cells - n_valid}; areal scale off by at most {worst:.4f}")

    sink_idx = None
    if sinks is not None:
        sids, sx, sy = read_points(sinks, id_col, x_col, y_col)
        _, _, cells = to_cells(transform, crs, z.shape, sx, sy, points_crs)
        bad = [i for i, rc in zip(sids, cells) if rc is None or not valid[rc]]
        if bad:
            sys.exit(f"sinks outside the valid data: {bad}")
        sink_idx = np.array([r * z.shape[1] + c for r, c in cells], dtype=np.int64)
    filled, d8, fd = flow(z, transform, sinks=sink_idx)
    upa = fd.upstream_area(unit="km2").astype("float64")
    if sink_idx is not None:
        for i, k in zip(sids, sink_idx):
            print(f"sink {i}: drains {upa.flat[k]:.3f} km2")
    upa[~valid] = np.nan
    cell_km2 = abs(transform.a * transform.e) / 1e6
    n_outlets = int(((d8 == 0) & valid).sum())
    print(f"outlets and pits (d8 = 0) on valid cells: {n_outlets}; largest upstream area {np.nanmax(upa):.3f} km2")

    stream = np.full(z.shape, np.nan)
    hand = np.full(z.shape, np.nan)
    if stream_km2 is not None:
        drain = valid & (upa >= stream_km2)
        stream = np.where(valid, drain.astype("float64"), np.nan)
        h = fd.hand(drain=drain, elevtn=np.where(valid, filled, NODATA))
        hand = np.where(valid, h, np.nan)
        print(f"stream cells (upstream area >= {stream_km2} km2): {int(drain.sum())}")

    bands = [upa, np.where(valid, d8, np.nan), stream, hand, np.where(valid, filled, np.nan)]
    prof = dict(driver="GTiff", height=z.shape[0], width=z.shape[1], count=len(bands), dtype="float32", crs=crs,
                transform=transform, nodata=np.nan, compress="deflate")
    with rasterio.open(out_path, "w", **prof) as dst:
        for i, b in enumerate(bands, 1):
            dst.write(b.astype("float32"), i)

    if points is None:
        return None
    ids, xs, ys = read_points(points, id_col, x_col, y_col)
    xs, ys, cells = to_cells(transform, crs, z.shape, xs, ys, points_crs)
    edges = edge_mask(valid)
    px = math.sqrt(abs(transform.a * transform.e))
    out = []
    for pid, x, y, rc in zip(ids, xs, ys, cells):
        rec = dict(id=pid, x=x, y=y, row="", col="", snapped=False, snap_m="", upstream_km2="", catchment_km2="",
                   catchment_cells="", edge_cells="")
        if rc is None:
            print(f"point {pid} is outside the DEM")
            out.append(rec)
            continue
        r, c = rc
        s = snap(upa, r, c, snap_m / px, snap_min_km2)
        if s is None:
            print(f"point {pid}: no cell with upstream area >= {snap_min_km2} km2 within {snap_m} m; no catchment")
            out.append(rec)
            continue
        rr, cc, d = s
        basin = fd.basins(idxs=np.array([rr * z.shape[1] + cc]), ids=np.array([1], dtype=np.int32)) == 1
        n = int(basin.sum())
        rec.update(row=rr, col=cc, snapped=True, snap_m=round(d * px, 1), upstream_km2=round(float(upa[rr, cc]), 4),
                   catchment_km2=round(n * cell_km2, 4), catchment_cells=n, edge_cells=int((basin & edges).sum()))
        if rec["edge_cells"]:
            print(f"point {pid}: its catchment touches the edge of the data in {rec['edge_cells']} cells; it may be cut")
        out.append(rec)
    n_snapped = sum(r["snapped"] for r in out)
    print(f"points {len(out)}: snapped {n_snapped}, not snapped {len(out) - n_snapped}")
    assert len(out) == len(ids)
    with open(str(out_path) + ".points.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dem")
    p.add_argument("--out", required=True)
    p.add_argument("--points")
    p.add_argument("--id", default="id")
    p.add_argument("--x", default="x")
    p.add_argument("--y", default="y")
    p.add_argument("--points-crs", help="CRS of the points' and sinks' x and y, if not the DEM's (EPSG:4326 for lon, lat)")
    p.add_argument("--sinks", help="CSV of closed-basin points (same columns as --points) where water leaves the surface")
    p.add_argument("--snap-m", type=float, default=300.0)
    p.add_argument("--snap-min-km2", type=float, default=1.0)
    p.add_argument("--stream-km2", type=float)
    p.add_argument("--max-scale-error", type=float, default=0.02)
    a = p.parse_args(argv)
    run(a.dem, a.out, a.points, a.id, a.x, a.y, a.points_crs, a.snap_m, a.snap_min_km2, a.stream_km2,
        a.max_scale_error, a.sinks)


if __name__ == "__main__":
    main()

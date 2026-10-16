"""Least accumulated cost from every cell of a cost raster to the nearest of one or more destinations.

The cost raster holds, in each cell, the cost of moving one metre of ground inside that cell (for
example seconds per metre, the inverse of a speed). Moving between the centres of two neighbouring
cells (8 neighbours) costs the step length in metres times the mean of the two cells' costs: half
of the straight segment between the centres lies in each cell. The search is a multi-source Dijkstra
from the destinations, so every cell gets the cost to its cheapest destination and that destination.

Cells are passable (a positive finite cost), barriers (--barrier-value), or NoData (the raster's
NoData value or NaN; impassable, with their own status, or --nodata stop). The raster's edge is not
crossed. A diagonal step between two cells whose two shared neighbours are both impassable is not
taken (--corner-rule both); --corner-rule either also refuses it when one of them is, and allow
always takes it.

The grid must be in a projected CRS: a geographic CRS, a rotated grid, or a projection whose scale
factor over the raster departs from 1 by more than --max-scale-error (Web Mercator away from the
equator) stops the run. Linear units other than metres are converted to metres.

Output: one GeoTIFF with three float64 bands, NoData NaN:
    1 accumulated cost, in the cost unit times metres (s/m gives seconds); NaN where no value
    2 index of the nearest destination (0-based, the order of the destinations table); -1 where none
    3 status: 1 reached, 2 unreachable (passable but cut off), 3 barrier, 4 NoData
and OUT.destinations.csv: index, id, x, y, row, col, cells (cells nearest to it).

Destinations: a CSV with an id and x, y in the raster's CRS. Each is placed at the centre of the cell
that holds it; the largest such shift is printed.

Usage:
    uvx --with numpy --with rasterio --with pyproj python cost_distance.py COST.tif DESTINATIONS.csv \\
        --cost-unit s/m --out OUT.tif [--id id --x x --y y] [--barrier-value V] \\
        [--nodata barrier|stop] [--corner-rule both|either|allow] [--max-scale-error 0.01]
"""

import argparse
import csv
import heapq
import math
from pathlib import Path

import numpy as np

REACHED, UNREACHABLE, BARRIER, NODATA = 1, 2, 3, 4


def grid_metres(crs, transform, height, width, max_scale_error=0.01):
    """Pixel width and height in metres, after checking that distances on the grid are distances on
    the ground: a CRS is set, the grid is not rotated, the CRS is projected, and the scale factor at
    nine points over the raster stays within max_scale_error of 1."""
    import pyproj

    if crs is None:
        raise SystemExit("the raster has no CRS; give it one before measuring distances on it")
    if transform.b != 0 or transform.d != 0:
        raise SystemExit(f"the grid is rotated or sheared (transform {tuple(transform)[:6]}); warp it to a "
                         "north-up grid first")
    c = pyproj.CRS.from_user_input(crs.to_wkt() if hasattr(crs, "to_wkt") else crs)
    if c.is_geographic:
        raise SystemExit(f"{c.name} is geographic (degrees); reproject the cost raster to a projected CRS in "
                         "metres suited to the area")
    units = {(a.unit_name, a.unit_conversion_factor) for a in c.axis_info[:2]}
    if len(units) != 1:
        raise SystemExit(f"the two axes of {c.name} have different units: {units}")
    unit_name, factor = units.pop()
    to_lonlat = pyproj.Transformer.from_crs(c, "EPSG:4326", always_xy=True)
    proj = pyproj.Proj(c)
    worst = 0.0
    for fr in (0.0, 0.5, 1.0):
        for fc in (0.0, 0.5, 1.0):
            x, y = transform @ (fc * width, fr * height)
            lon, lat = to_lonlat.transform(x, y)
            f = proj.get_factors(lon, lat)
            for s in (f.meridional_scale, f.parallel_scale):
                if abs(s - 1) > abs(worst):
                    worst = s - 1
    if abs(worst) > max_scale_error:
        raise SystemExit(f"the scale factor of {c.name} departs from 1 by {worst:+.4f} over the raster "
                         f"(--max-scale-error {max_scale_error}); grid metres are not ground metres here. "
                         "Reproject to a CRS with little distortion over the area (a UTM zone, a national grid)")
    return {"dx": abs(transform.a) * factor, "dy": abs(transform.e) * factor, "unit": unit_name,
            "scale_error": worst, "crs": c.name}


def _steps(dx, dy):
    return [(dr, dc, math.hypot(dr * dy, dc * dx)) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]


def solve(cost, passable, dx, dy, sources, corner="both", nodata=None):
    """Multi-source Dijkstra on the 8-neighbour grid.

    cost: cost per metre in each cell (read only where passable). passable: bool array. dx, dy: pixel
    width and height in metres. sources: (row, col) of each destination, in order; a tie between two
    destinations goes to the one listed first. corner: 'both', 'either' or 'allow' (see the module
    docstring). nodata: bool array of NoData cells (they must not be passable), for the status only.

    Returns accumulated (inf where not reached), nearest (index into sources, -1 where none) and status.
    """
    if corner not in ("both", "either", "allow"):
        raise SystemExit(f"unknown corner rule {corner}")
    cost = np.asarray(cost, float)
    passable = np.asarray(passable, bool)
    h, w = cost.shape
    if not (np.isfinite(cost[passable]).all() and (cost[passable] > 0).all()):
        raise SystemExit("every passable cell needs a positive finite cost")
    seen = {}
    for i, (r, c) in enumerate(sources):
        if not (0 <= r < h and 0 <= c < w):
            raise SystemExit(f"destination {i} at row {r}, col {c} is outside the raster")
        if not passable[r, c]:
            raise SystemExit(f"destination {i} at row {r}, col {c} is on a barrier or NoData cell")
        if (r, c) in seen:
            raise SystemExit(f"destinations {seen[(r, c)]} and {i} fall in the same cell (row {r}, col {c}); "
                             "merge them or use a finer raster")
        seen[(r, c)] = i

    acc = np.full((h, w), np.inf)
    nearest = np.full((h, w), -1, int)
    done = np.zeros((h, w), bool)
    heap = []
    for i, (r, c) in enumerate(sources):
        acc[r, c], nearest[r, c] = 0.0, i
        heap.append((0.0, i, r, c))
    heapq.heapify(heap)
    steps = _steps(dx, dy)
    while heap:
        a, src, r, c = heapq.heappop(heap)
        if done[r, c] or a > acc[r, c] or src != nearest[r, c]:
            continue
        done[r, c] = True
        here = cost[r, c]
        for dr, dc, d in steps:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < h and 0 <= cc < w) or done[rr, cc] or not passable[rr, cc]:
                continue
            if dr and dc and corner != "allow":
                side_a, side_b = passable[r + dr, c], passable[r, c + dc]
                if (corner == "both" and not side_a and not side_b) or (corner == "either" and not (side_a and side_b)):
                    continue
            v = a + d * (here + cost[rr, cc]) / 2
            if v < acc[rr, cc] or (v == acc[rr, cc] and src < nearest[rr, cc]):
                acc[rr, cc], nearest[rr, cc] = v, src
                heapq.heappush(heap, (v, src, rr, cc))

    status = np.full((h, w), BARRIER, np.uint8)
    status[passable] = UNREACHABLE
    status[np.isfinite(acc)] = REACHED
    if nodata is not None:
        status[np.asarray(nodata, bool)] = NODATA
    return {"accumulated": acc, "nearest": nearest, "status": status}


def read_cost(path, band=1, barrier_value=None):
    """The band as float64, and boolean arrays of passable, barrier and NoData cells. Stops on cells
    that are none of these (zero, negative or infinite costs)."""
    import rasterio

    with rasterio.open(path) as ds:
        a = ds.read(band).astype(float)
        nd = ds.nodatavals[band - 1]
        meta = {"crs": ds.crs, "transform": ds.transform, "height": ds.height, "width": ds.width}
    nodata = np.isnan(a)
    if nd is not None and not (isinstance(nd, float) and math.isnan(nd)):
        nodata |= a == nd
    barrier = np.zeros(a.shape, bool)
    if barrier_value is not None:
        barrier = (a == barrier_value) & ~nodata
    passable = ~nodata & ~barrier
    bad = passable & ~(np.isfinite(a) & (a > 0))
    if bad.any():
        raise SystemExit(f"{int(bad.sum())} cells have a cost that is zero, negative or infinite (e.g. "
                         f"{a[bad][:3].tolist()}); declare barriers with --barrier-value, NoData in the raster")
    return a, passable, barrier, nodata, meta


def read_destinations(path, id_col, x_col, y_col):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for k in (id_col, x_col, y_col):
        if rows and k not in rows[0]:
            raise SystemExit(f"{path} has no column {k}; columns: {list(rows[0])}")
    if not rows:
        raise SystemExit(f"{path} has no destinations")
    return [(r[id_col], float(r[x_col]), float(r[y_col])) for r in rows]


def place(destinations, transform, height, width):
    """(row, col) of the cell holding each destination, and the distance in CRS units from each to its
    cell's centre. Stops on destinations outside the raster."""
    inv = ~transform
    cells, shifts, outside = [], [], []
    for did, x, y in destinations:
        col_f, row_f = inv @ (x, y)
        r, c = math.floor(row_f), math.floor(col_f)
        if not (0 <= r < height and 0 <= c < width):
            outside.append(did)
            continue
        cx, cy = transform @ (c + 0.5, r + 0.5)
        cells.append((r, c))
        shifts.append(math.hypot(x - cx, y - cy))
    if outside:
        raise SystemExit(f"{len(outside)} destinations are outside the raster: {outside[:5]}")
    return cells, shifts


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cost")
    p.add_argument("destinations")
    p.add_argument("--cost-unit", required=True, help="the unit of the cost per metre, ending in /m (s/m, min/m)")
    p.add_argument("--out", required=True)
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--id", default="id")
    p.add_argument("--x", default="x")
    p.add_argument("--y", default="y")
    p.add_argument("--barrier-value", type=float)
    p.add_argument("--nodata", choices=["barrier", "stop"], default="barrier")
    p.add_argument("--corner-rule", choices=["both", "either", "allow"], default="both")
    p.add_argument("--max-scale-error", type=float, default=0.01)
    a = p.parse_args()
    if not a.cost_unit.endswith("/m") or a.cost_unit == "/m":
        p.error("--cost-unit must be a cost per metre, such as s/m")
    out_unit = a.cost_unit[:-2]

    cost, passable, barrier, nodata, meta = read_cost(a.cost, a.band, a.barrier_value)
    if a.nodata == "stop" and nodata.any():
        raise SystemExit(f"{int(nodata.sum())} NoData cells and --nodata stop")
    g = grid_metres(meta["crs"], meta["transform"], meta["height"], meta["width"], a.max_scale_error)
    dests = read_destinations(a.destinations, a.id, a.x, a.y)
    cells, shifts = place(dests, meta["transform"], meta["height"], meta["width"])
    res = solve(cost, passable, g["dx"], g["dy"], cells, a.corner_rule, nodata)

    st = res["status"]
    counts = {name: int((st == code).sum()) for name, code in
              (("reached", REACHED), ("unreachable", UNREACHABLE), ("barrier", BARRIER), ("nodata", NODATA))}
    if sum(counts.values()) != st.size:
        raise SystemExit(f"status counts {counts} do not add up to {st.size} cells")
    print(f"cost: {a.cost}, {meta['height']} x {meta['width']}, CRS {g['crs']} ({g['unit']}), pixel "
          f"{g['dx']:.4g} m x {g['dy']:.4g} m, largest scale error {g['scale_error']:+.5f}")
    print(f"cost unit {a.cost_unit}, accumulated cost in {out_unit}; corner rule {a.corner_rule}, "
          f"NoData {a.nodata}")
    print(f"cells {st.size}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"destinations {len(dests)}; largest shift to a cell centre {max(shifts) * g['dx'] / abs(meta['transform'].a):.4g} m")
    reached = res["accumulated"][st == REACHED]
    print(f"accumulated cost ({out_unit}) over reached cells: min {reached.min():.6g}, "
          f"median {np.median(reached):.6g}, max {reached.max():.6g}")

    import rasterio

    acc = np.where(st == REACHED, res["accumulated"], np.nan)
    profile = {"driver": "GTiff", "height": meta["height"], "width": meta["width"], "count": 3, "dtype": "float64",
               "crs": meta["crs"], "transform": meta["transform"], "nodata": float("nan")}
    with rasterio.open(a.out, "w", **profile) as ds:
        ds.write(acc, 1)
        ds.write(res["nearest"].astype(float), 2)
        ds.write(st.astype(float), 3)
        for i, name in enumerate((f"accumulated_cost_{out_unit}", "nearest_destination", "status"), 1):
            ds.set_band_description(i, name)
    mapping = Path(a.out).with_suffix(".destinations.csv")
    with open(mapping, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["index", "id", "x", "y", "row", "col", "cells"])
        for i, ((did, x, y), (r, c)) in enumerate(zip(dests, cells)):
            wr.writerow([i, did, x, y, r, c, int((res["nearest"] == i).sum())])
    print(f"wrote {a.out} and {mapping}")


if __name__ == "__main__":
    main()

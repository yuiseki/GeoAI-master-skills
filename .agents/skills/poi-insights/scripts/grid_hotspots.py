"""Count points in H3 or S2 cells and find where they gather: Getis-Ord Gi* over every cell of the study area
(the empty cells too), Benjamini-Hochberg over the one-sided p-values, and clusters as connected hot cells.

    uvx --with h3 --with s2sphere --with numpy --with scipy --with duckdb python grid_hotspots.py POINTS.parquet OUTDIR \
        --grid h3 --res 9 --bbox W S E N [--k 1] [--alpha 0.05] [--group brand]

POINTS.parquet needs lon and lat (the output of poi_extract.py has them). Writes OUTDIR/cells.csv (cell, count,
z, p, hot, cluster, and counts per --group value), OUTDIR/clusters.csv (rank, cells, points, centre) and
OUTDIR/audit.json.

Gi* uses binary weights over the k-ring (the cell and its neighbours within k steps), the study area being every
cell whose centre is in the box and every cell that holds a point of the box. A cell is hot when the Benjamini-Hochberg procedure keeps it at --alpha among all
cells of the area, and it holds at least one point. Hot cells that touch (k = 1 ring) form one cluster; clusters
are ranked by their points. For S2 the cells are counted but Gi* is not run (the area's cells and their
neighbours are only built for H3 here).
"""

import argparse
import json
import math
import os
import sys

import numpy as np


def assign(lon, lat, grid, res):
    """The cell of each point: an H3 index, or an S2 cell token at level res."""
    if grid == "h3":
        import h3
        return [h3.latlng_to_cell(float(y), float(x), res) for x, y in zip(lon, lat)]
    if grid == "s2":
        import s2sphere
        return [s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees(float(y), float(x))).parent(res).to_token()
                for x, y in zip(lon, lat)]
    raise ValueError(grid)


def study_cells(bbox, res):
    """Every H3 cell whose centre is in the box."""
    import h3
    w, s, e, n = bbox
    poly = h3.LatLngPoly([(s, w), (s, e), (n, e), (n, w)])
    return sorted(h3.h3shape_to_cells(poly, res))


def gi_star(x, neighbours):
    """Gi* z-scores with binary weights that include the cell itself. neighbours[i]: indices j with w_ij = 1."""
    x = np.asarray(x, float)
    n = len(x)
    xbar = x.mean()
    s = math.sqrt(max((x ** 2).mean() - xbar ** 2, 0.0))
    z = np.zeros(n)
    if s == 0:
        return z
    for i in range(n):
        nb = neighbours[i]
        w = len(nb)
        den = s * math.sqrt(max(n * w - w * w, 0) / (n - 1))
        z[i] = (x[nb].sum() - xbar * w) / den if den > 0 else 0.0
    return z


def bh_reject(p, alpha):
    """Benjamini-Hochberg: which hypotheses are rejected at false discovery rate alpha."""
    p = np.asarray(p, float)
    order = np.argsort(p)
    m = len(p)
    passed = p[order] <= alpha * np.arange(1, m + 1) / m
    k = np.nonzero(passed)[0].max() + 1 if passed.any() else 0
    out = np.zeros(m, bool)
    out[order[:k]] = True
    return out


def clusters(hot, counts, grid):
    """Connected components of the hot cells (H3 neighbours at distance 1), largest number of points first."""
    import h3
    hot, seen, out = set(hot), set(), []
    for c in sorted(hot):
        if c in seen:
            continue
        stack, comp = [c], []
        seen.add(c)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in h3.grid_ring(u, 1):
                if v in hot and v not in seen:
                    seen.add(v)
                    stack.append(v)
        pts = sum(counts.get(u, 0) for u in comp)
        lat = sum(h3.cell_to_latlng(u)[0] * counts.get(u, 0) for u in comp) / max(pts, 1)
        lon = sum(h3.cell_to_latlng(u)[1] * counts.get(u, 0) for u in comp) / max(pts, 1)
        out.append({"cells": len(comp), "points": pts, "lat": lat, "lon": lon, "members": sorted(comp)})
    out.sort(key=lambda d: (-d["points"], d["members"][0]))
    return out


def hotspots(lon, lat, grid, res, bbox, k=1, alpha=0.05):
    from scipy.stats import norm
    cells_of = assign(lon, lat, grid, res)
    counts = {}
    for c in cells_of:
        counts[c] = counts.get(c, 0) + 1
    audit = {"points": len(cells_of)}
    if grid != "h3":
        audit.update(cells=len(counts), outside=0)
        return {"counts": counts, "cells": sorted(counts), "z": None, "hot": set(), "clusters": [], "audit": audit}
    import h3
    w, s, e, n = bbox
    inside = [w <= x <= e and s <= y <= n for x, y in zip(lon, lat)]
    outside = len(inside) - sum(inside)
    counts = {}
    for c, ok in zip(cells_of, inside):
        if ok:
            counts[c] = counts.get(c, 0) + 1
    # The area: every cell whose centre is in the box, and the cells of the points in the box near its edge.
    area = sorted(set(study_cells(bbox, res)) | set(counts))
    index = {c: i for i, c in enumerate(area)}
    x = np.array([counts.get(c, 0) for c in area], float)
    nb = [[index[v] for v in h3.grid_disk(c, k) if v in index] for c in area]
    z = gi_star(x, nb)
    p = norm.sf(z)
    rej = bh_reject(p, alpha)
    hot = {c for c, r, xi in zip(area, rej, x) if r and xi > 0}
    audit.update(cells=len(area), outside=outside, hot_cells=len(hot))
    return {"counts": counts, "cells": area, "z": dict(zip(area, z)), "p": dict(zip(area, p)), "hot": hot,
            "clusters": clusters(hot, counts, grid), "audit": audit}


def main(argv=None):
    import duckdb
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("points")
    a.add_argument("outdir")
    a.add_argument("--grid", choices=["h3", "s2"], default="h3")
    a.add_argument("--res", type=int, default=9)
    a.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("W", "S", "E", "N"))
    a.add_argument("--k", type=int, default=1)
    a.add_argument("--alpha", type=float, default=0.05)
    a.add_argument("--group", help="a column to count per cell as well (brand, category)")
    a = a.parse_args(argv)
    con = duckdb.connect()
    gcol = f", coalesce(cast({a.group} as varchar), '(none)')" if a.group else ""
    rows = con.execute(f"select lon, lat{gcol} from read_parquet('{a.points}')").fetchall()
    lon = [r[0] for r in rows]
    lat = [r[1] for r in rows]
    res = hotspots(lon, lat, a.grid, a.res, a.bbox, a.k, a.alpha)
    os.makedirs(a.outdir, exist_ok=True)
    groups = {}
    if a.group:
        for c, r in zip(assign(lon, lat, a.grid, a.res), rows):
            groups.setdefault(c, {}).setdefault(r[2], 0)
            groups[c][r[2]] += 1
    member = {m: i + 1 for i, cl in enumerate(res["clusters"]) for m in cl["members"]}
    with open(os.path.join(a.outdir, "cells.csv"), "w", encoding="utf-8") as f:
        f.write("cell,count,z,p,hot,cluster" + (",groups" if a.group else "") + "\n")
        for c in sorted(set(res["cells"]) | set(res["counts"])):
            z = res["z"].get(c) if res["z"] else None
            p = res["p"].get(c) if res["z"] else None
            g = ";".join(f"{k}={v}" for k, v in sorted(groups.get(c, {}).items())) if a.group else None
            f.write(f"{c},{res['counts'].get(c, 0)},{'' if z is None else f'{z:.4f}'},"
                    f"{'' if p is None else f'{p:.3g}'},{int(c in res['hot'])},{member.get(c, '')}"
                    + (f',"{g}"' if a.group else "") + "\n")
    with open(os.path.join(a.outdir, "clusters.csv"), "w", encoding="utf-8") as f:
        f.write("rank,cells,points,lat,lon\n")
        for i, cl in enumerate(res["clusters"], 1):
            f.write(f"{i},{cl['cells']},{cl['points']},{cl['lat']:.6f},{cl['lon']:.6f}\n")
    audit = {**res["audit"], "grid": a.grid, "res": a.res, "bbox": a.bbox, "k": a.k, "alpha": a.alpha,
             "clusters": len(res["clusters"]), "points_file": a.points}
    with open(os.path.join(a.outdir, "audit.json"), "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=1)
    print(json.dumps(audit))


if __name__ == "__main__":
    sys.exit(main())

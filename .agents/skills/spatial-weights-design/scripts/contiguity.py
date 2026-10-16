"""Neighbours of polygons by shared boundary: Queen (any shared point) or Rook (a shared edge of some length).

Polygons drawn separately rarely share boundaries exactly: a hairline gap makes neighbours look apart, a
hairline overlap makes them look overlapping. --tolerance snaps every coordinate to that grid first
(shapely.set_precision), which closes gaps narrower than it. Overlapping borders count as shared: two
polygons are Rook neighbours when their intersection has length or area, Queen neighbours when they
intersect at all.

Prints the number of neighbours (min, median, max), the islands (no neighbour) and the connected
components; with --out, writes one row per pair (id, neighbour), both directions.

Usage:
    uvx --from 'duckdb>=1.5.5' --with shapely --with numpy --with pyarrow python contiguity.py POLYGONS ID \\
        [--geom geometry] [--rule queen|rook] [--tolerance 0] [--out pairs.parquet]
"""

import argparse

import numpy as np
import shapely
from shapely.strtree import STRtree


def contiguity(geoms, rule="queen", tolerance=0.0):
    if rule not in ("queen", "rook"):
        raise SystemExit("--rule must be queen or rook")
    g = [shapely.set_precision(x, tolerance) if tolerance else x for x in geoms]
    tree = STRtree(g)
    nb = {i: [] for i in range(len(g))}
    for i, j in zip(*tree.query(g, predicate="intersects")):
        if i >= j:
            continue
        if rule == "rook":
            inter = shapely.intersection(g[i], g[j])
            if inter.length <= 0 and inter.area <= 0:
                continue
        nb[int(i)].append(int(j))
        nb[int(j)].append(int(i))
    return {i: sorted(v) for i, v in nb.items()}


def components(nb):
    seen, out = set(), []
    for start in nb:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            k = stack.pop()
            comp.append(k)
            for m in nb[k]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        out.append(sorted(comp))
    return out


def main():
    import duckdb
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("polygons")
    p.add_argument("id")
    p.add_argument("--geom", default="geometry")
    p.add_argument("--rule", default="queen", choices=("queen", "rook"))
    p.add_argument("--tolerance", type=float, default=0.0)
    p.add_argument("--out")
    a = p.parse_args()
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    rows = con.sql(f'select "{a.id}", ST_AsWKB("{a.geom}") from \'{a.polygons}\'').fetchall()
    ids = [r[0] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{a.id} is not unique")
    nb = contiguity([shapely.from_wkb(bytes(r[1])) for r in rows], a.rule, a.tolerance)
    counts = np.array([len(v) for v in nb.values()])
    comps = components(nb)
    print(f"units {len(ids)}, rule {a.rule}, tolerance {a.tolerance}: neighbours min {counts.min()} "
          f"median {np.median(counts):g} max {counts.max()}; pairs {int(counts.sum()) // 2}; islands {int((counts == 0).sum())}; "
          f"components {len(comps)} (largest {max(len(c) for c in comps)})")
    if a.out:
        import pyarrow as pa
        import pyarrow.parquet as pq
        pairs = [(ids[i], ids[j]) for i, v in nb.items() for j in v]
        pq.write_table(pa.table({"id": [x for x, _ in pairs], "neighbour": [y for _, y in pairs]}), a.out)


if __name__ == "__main__":
    main()

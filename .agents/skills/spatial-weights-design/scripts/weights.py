"""Design spatial weights (W) before using them: build candidate neighbour structures, describe each, and
compare them.

Candidates (any number, side by side):
    --knn K ...      the K nearest other units (asymmetric: j can be i's neighbour without i being j's)
    --band D ...     every unit within distance D (islands where units are sparse)
    --decay power|exponential with --band: weights falling with distance inside the band
    --queen/--rook   polygons sharing a boundary point / an edge (needs --geometry; contiguity.py)

For each: units, neighbours per unit (min, median, max), islands, connected components, the share of
directed pairs not returned (asymmetry), the distances to neighbours, and the smallest band that leaves no
island (the largest nearest-neighbour distance). With --value, Moran's I of that column under binary and
row-standardised versions of each W: if they differ much, the choice of standardisation is part of the
conclusion. Jaccard overlap of the neighbour sets between every two candidates.

Distances: --x/--y in a projected CRS (--crs-units m or km), or --lon/--lat on the sphere (km). Bands are in
those units. Never pass degrees as --x/--y. The distance matrix is held in memory: up to 20,000 units.

Usage:
    uvx --with numpy --with scipy --with duckdb --with pyarrow python weights.py TABLE ID \\
        (--x X --y Y --crs-units m | --lon LON --lat LAT) [--knn 4 8] [--band 2000 5000] \\
        [--decay power --alpha 1] [--value COL] [--out w.parquet]
"""

import argparse
import math

import numpy as np
from scipy import sparse

EARTH_KM = 6371.0
MAX_UNITS = 20_000


class Neighbours(list):
    """Neighbour index arrays per unit, with the distances to them and each unit's nearest distance."""

    def __init__(self, nb, dist, nn):
        super().__init__(nb)
        self.dist, self.nn = dist, nn


def distances(x, y, lonlat=False):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) > MAX_UNITS:
        raise SystemExit(f"{len(x)} units; this script holds an n x n distance matrix, up to {MAX_UNITS}")
    if lonlat:
        lo, la = np.radians(x), np.radians(y)
        a = (np.sin((la[:, None] - la[None]) / 2) ** 2
             + np.cos(la[:, None]) * np.cos(la[None]) * np.sin((lo[:, None] - lo[None]) / 2) ** 2)
        return 2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return np.hypot(x[:, None] - x[None], y[:, None] - y[None])


def _nn(D):
    E = D + np.diag(np.full(len(D), np.inf))
    return E.min(1)


def knn(D, k):
    n = len(D)
    if k >= n:
        raise SystemExit(f"k {k} needs more than {k} units; there are {n}")
    E = D + np.diag(np.full(n, np.inf))
    idx = np.argsort(E, axis=1, kind="stable")[:, :k]
    nb = Neighbours([np.sort(r) for r in idx], None, _nn(D))
    nb.dist = [D[i, nb[i]] for i in range(n)]
    return nb, nb.dist


def band(D, d, decay=None, alpha=1.0, scale=None):
    n = len(D)
    nb, dist, w = [], [], []
    for i in range(n):
        j = np.flatnonzero((D[i] <= d) & (np.arange(n) != i))
        nb.append(j)
        dist.append(D[i, j])
        if decay == "power":
            if (D[i, j] <= 0).any():
                raise SystemExit("power decay at distance 0 is infinite; units share a location")
            w.append(D[i, j] ** -alpha)
        elif decay == "exponential":
            w.append(np.exp(-D[i, j] / scale))
        else:
            w.append(np.ones(len(j)))
    return Neighbours(nb, dist, _nn(D)), w


def _components(nb):
    n = len(nb)
    adj = sparse.lil_matrix((n, n))
    for i, js in enumerate(nb):
        adj[i, js] = 1
    k, _ = sparse.csgraph.connected_components(adj.tocsr(), directed=False)
    return int(k)


def describe(nb, dist=None):
    deg = np.array([len(j) for j in nb])
    pairs = {(i, int(j)) for i, js in enumerate(nb) for j in js}
    asym = sum((j, i) not in pairs for i, j in pairs) / len(pairs) if pairs else float("nan")
    out = {"units": len(nb), "degree_min": int(deg.min()), "degree_median": float(np.median(deg)),
           "degree_max": int(deg.max()), "islands": int((deg == 0).sum()), "components": _components(nb),
           "asymmetric_share": asym}
    dist = dist if dist is not None else getattr(nb, "dist", None)
    if dist is not None:
        flat = np.concatenate([np.asarray(d, float) for d in dist]) if pairs else np.array([np.nan])
        out.update(distance_median=float(np.median(flat)), distance_max=float(flat.max()))
    if getattr(nb, "nn", None) is not None:
        out["band_without_islands"] = float(nb.nn.max())
    return out


def standardise(nb, w, kind):
    """binary (1 for a neighbour), weights (as given), row (each row sums to 1; islands stay 0), symmetric
    (binary, i and j neighbours when either lists the other)."""
    n = len(nb)
    rows = np.concatenate([np.full(len(j), i) for i, j in enumerate(nb)]) if n else np.array([], int)
    cols = np.concatenate([np.asarray(j, int) for j in nb]) if n else np.array([], int)
    vals = np.concatenate([np.asarray(v, float) for v in w]) if n else np.array([])
    if kind in ("binary", "symmetric"):
        vals = np.ones_like(vals)
    W = sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))
    if kind == "symmetric":
        W = ((W + W.T) > 0).astype(float)
    elif kind == "row":
        s = np.asarray(W.sum(1)).ravel()
        inv = np.divide(1.0, s, out=np.zeros_like(s), where=s > 0)
        W = sparse.diags(inv) @ W
    elif kind not in ("binary", "weights"):
        raise SystemExit(f"unknown standardisation {kind}")
    return W.tocsr()


def moran_i(x, W):
    x = np.asarray(x, float)
    z = x - x.mean()
    s0 = W.sum()
    if s0 == 0:
        raise SystemExit("no unit has a neighbour")
    return float(len(x) / s0 * (z @ (W @ z)) / (z @ z))


def jaccard(a, b):
    out = []
    for x, y in zip(a, b):
        sx, sy = set(np.asarray(x).tolist()), set(np.asarray(y).tolist())
        out.append(len(sx & sy) / len(sx | sy) if sx | sy else 1.0)
    return float(np.mean(out))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("--x")
    p.add_argument("--y")
    p.add_argument("--crs-units", choices=["m", "km"])
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--geometry")
    p.add_argument("--knn", type=int, nargs="*", default=[])
    p.add_argument("--band", type=float, nargs="*", default=[])
    p.add_argument("--decay", choices=["power", "exponential"])
    p.add_argument("--alpha", type=float, default=1.0)
    p.add_argument("--scale", type=float)
    p.add_argument("--queen", action="store_true")
    p.add_argument("--rook", action="store_true")
    p.add_argument("--value")
    p.add_argument("--out")
    a = p.parse_args()
    if a.decay == "exponential" and a.scale is None:
        p.error("--decay exponential needs --scale")

    import duckdb

    con = duckdb.connect()
    cols = [f'"{a.id}"']
    if a.lon:
        cols += [f'"{a.lon}"', f'"{a.lat}"']
        unit, lonlat = "km (great circle)", True
    elif a.x:
        if not a.crs_units:
            p.error("--x/--y need --crs-units (m or km) of a projected CRS; do not pass degrees")
        cols += [f'"{a.x}"', f'"{a.y}"']
        unit, lonlat = a.crs_units, False
    elif not a.geometry:
        p.error("give --x/--y, --lon/--lat, or --geometry")
    if a.value:
        cols.append(f'"{a.value}"')
    rows = con.sql(f"select {', '.join(cols)} from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("missing values in the columns used; drop those rows first")
    ids = [r[0] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{a.id} is not unique")
    value = np.array([r[-1] for r in rows], float) if a.value else None

    cands = {}
    if a.knn or a.band:
        if not (a.lon or a.x):
            p.error("--knn and --band need --x/--y or --lon/--lat")
        D = distances([r[1] for r in rows], [r[2] for r in rows], lonlat)
        for k in a.knn:
            nb, _ = knn(D, k)
            cands[f"knn {k}"] = (nb, [np.ones(len(j)) for j in nb])
        for d in a.band:
            nb, w = band(D, d, a.decay, a.alpha, a.scale)
            cands[f"band {d:g}" + (f" {a.decay}" if a.decay else "")] = (nb, w)
    if a.queen or a.rook:
        if not a.geometry:
            p.error("--queen/--rook need --geometry")
        import shapely

        from contiguity import contiguity

        con.sql("install spatial; load spatial;")
        g = [shapely.from_wkb(bytes(r[0])) for r in con.sql(f'select ST_AsWKB("{a.geometry}") from \'{a.table}\'').fetchall()]
        for rule in [r for r, on in (("queen", a.queen), ("rook", a.rook)) if on]:
            d = contiguity(g, rule)
            nb = [np.array(d[i], int) for i in range(len(g))]
            cands[rule] = (nb, [np.ones(len(j)) for j in nb])
    if not cands:
        p.error("give at least one candidate (--knn, --band, --queen, --rook)")

    print(f"units {len(ids)}, distances in {unit if (a.lon or a.x) else 'n/a'}")
    for name, (nb, w) in cands.items():
        s = describe(nb)
        line = (f"{name}: neighbours min {s['degree_min']} median {s['degree_median']:g} max {s['degree_max']}, "
                f"islands {s['islands']}, components {s['components']}, asymmetric {s['asymmetric_share']:.3f}")
        if "distance_median" in s:
            line += f", neighbour distance median {s['distance_median']:.4g} max {s['distance_max']:.4g}"
        if "band_without_islands" in s:
            line += f", smallest band without islands {s['band_without_islands']:.4g}"
        print(line)
        if value is not None and s["islands"] < s["units"]:
            ib = moran_i(value, standardise(nb, w, "binary"))
            ir = moran_i(value, standardise(nb, w, "row"))
            extra = f", given weights {moran_i(value, standardise(nb, w, 'weights')):+.3f}" if a.decay else ""
            print(f"  Moran's I of {a.value}: binary {ib:+.3f}, row-standardised {ir:+.3f}{extra}")
    names = list(cands)
    if len(names) > 1:
        print("Jaccard overlap of neighbour sets (mean over units):")
        for i, x in enumerate(names):
            for y in names[i + 1:]:
                print(f"  {x} vs {y}: {jaccard(cands[x][0], cands[y][0]):.3f}")
    if a.out:
        import pyarrow as pa

        recs = [(name, str(ids[i]), str(ids[int(j)]), float(wt)) for name, (nb, w) in cands.items()
                for i, (js, ws) in enumerate(zip(nb, w)) for j, wt in zip(js, ws)]
        t = pa.table({"candidate": [r[0] for r in recs], "id": [r[1] for r in recs],
                      "neighbour": [r[2] for r in recs], "weight": [r[3] for r in recs]})
        con.sql(f"copy (select * from t order by all) to '{a.out}' (format parquet)")
        print(f"wrote {len(recs)} directed pairs to {a.out}")


if __name__ == "__main__":
    main()

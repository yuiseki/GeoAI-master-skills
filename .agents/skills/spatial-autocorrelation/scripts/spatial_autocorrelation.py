"""Spatial autocorrelation of one value: global Moran's I, a correlogram by distance band, and
local Moran (LISA) clusters.

Neighbours are taken by great-circle distance (sphere of radius 6,371 km), so they are right at any
latitude and across the antimeridian. Weights are row-standardised; a unit with no neighbour has a
zero row, as in PySAL. Pseudo p-values come from permutations and are folded (one-sided in the
direction of the observed value), as esda 2.10 does by default (its alternative='directed'); esda
announces a move to two-sided, which roughly doubles a p-value.

Usage:
    uvx --with duckdb --with scikit-learn --with pyarrow python spatial_autocorrelation.py \
        TABLE ID VALUE (--lon COL --lat COL | --geometry COL) [--k 6] \
        [--bands-km 0 500 1000 2000 4000] [--permutations 999] [--local-out lisa.parquet] \
        [--hotspots-out gi.parquet]

VALUE can be a target, a feature, or a model's residual (target - prediction).
"""

import argparse

import numpy as np
from scipy import sparse
from sklearn.neighbors import BallTree

EARTH_KM = 6371.0


def _tree(lon, lat):
    # BallTree's haversine takes (latitude, longitude) in radians.
    return BallTree(np.radians(np.c_[lat, lon]), metric="haversine")


def knn_neighbors(lon, lat, k):
    """For each unit, the indices of its k nearest other units."""
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    _, idx = _tree(lon, lat).query(np.radians(np.c_[lat, lon]), k=k + 1)
    out = []
    for i, row in enumerate(idx):
        row = [j for j in row if j != i][:k]
        out.append(np.array(row, int))
    return out


def band_neighbors(lon, lat, lo_km, hi_km):
    """For each unit, the indices of the other units at a distance in (lo_km, hi_km]."""
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    pts = np.radians(np.c_[lat, lon])
    idx, dist = _tree(lon, lat).query_radius(pts, r=hi_km / EARTH_KM, return_distance=True)
    out = []
    for i, (row, d) in enumerate(zip(idx, dist)):
        keep = (row != i) & (d * EARTH_KM > lo_km)
        out.append(np.sort(row[keep]))
    return out


def _weights(neighbors):
    n = len(neighbors)
    rows, cols, vals = [], [], []
    for i, nb in enumerate(neighbors):
        if len(nb):
            rows.extend([i] * len(nb))
            cols.extend(nb.tolist())
            vals.extend([1.0 / len(nb)] * len(nb))
    return sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))


def _fold(sim, observed):
    larger = int((sim >= observed).sum())
    if len(sim) - larger < larger:
        larger = len(sim) - larger
    return (larger + 1.0) / (len(sim) + 1.0)


def moran(x, neighbors, permutations=999, seed=0):
    x = np.asarray(x, float)
    n = len(x)
    W = _weights(neighbors)
    s0 = W.sum()
    if s0 == 0:
        raise SystemExit("no unit has a neighbour")

    def stat(v):
        z = v - v.mean()
        return n / s0 * (z @ (W @ z)) / (z @ z)

    observed = stat(x)
    rng = np.random.default_rng(seed)
    sim = np.array([stat(rng.permutation(x)) for _ in range(permutations)])
    return {"I": float(observed), "EI": -1.0 / (n - 1), "p_sim": _fold(sim, observed),
            "n": n, "islands": int(sum(len(nb) == 0 for nb in neighbors))}


def local_moran(x, neighbors, permutations=999, seed=0):
    """Local Moran's I per unit, its quadrant (1 HH, 2 LH, 3 LL, 4 HL) and a conditional
    permutation pseudo p-value (the unit's own value fixed, its neighbours drawn from the rest)."""
    x = np.asarray(x, float)
    n = len(x)
    z = x - x.mean()
    den = (z * z).sum()
    lag = _weights(neighbors) @ z
    Is = (n - 1) * z * lag / den
    q = np.where(z > 0, np.where(lag > 0, 1, 4), np.where(lag > 0, 2, 3))
    rng = np.random.default_rng(seed)
    p = np.ones(n)
    others = np.arange(n)
    for i, nb in enumerate(neighbors):
        k = len(nb)
        if k == 0:
            continue
        pool = np.delete(others, i)
        draws = np.array([rng.choice(pool, size=k, replace=False) for _ in range(permutations)])
        sim = (n - 1) * z[i] * z[draws].mean(axis=1) / den
        p[i] = _fold(sim, Is[i])
    return {"Is": Is, "q": q, "p_sim": p, "lag": lag}


def getis_ord(x, neighbors):
    """Getis-Ord Gi* z-score per unit: is the sum over the unit and its neighbours (binary
    weights, the unit included) higher or lower than the overall mean would give?"""
    x = np.asarray(x, float)
    n = len(x)
    xbar = x.mean()
    s = np.sqrt((x ** 2).mean() - xbar ** 2)
    z = np.empty(n)
    for i, nb in enumerate(neighbors):
        idx = np.r_[i, nb]
        wsum = len(idx)  # binary weights: the sum and the sum of squares are both the count
        num = x[idx].sum() - xbar * wsum
        den = s * np.sqrt((n * wsum - wsum ** 2) / (n - 1))
        z[i] = num / den
    return z


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("value")
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--geometry")
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--bands-km", type=float, nargs="+")
    p.add_argument("--permutations", type=int, default=999)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--local-out")
    p.add_argument("--hotspots-out", help="write Getis-Ord Gi* z-scores per unit")
    a = p.parse_args()

    import duckdb

    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    if a.geometry:
        pt = f'ST_PointOnSurface("{a.geometry}")'
        xy = f"ST_X({pt}) as lon, ST_Y({pt}) as lat"
    elif a.lon:
        xy = f'"{a.lon}" as lon, "{a.lat}" as lat'
    else:
        raise SystemExit("give --lon and --lat, or --geometry")
    t = con.sql(f'select "{a.id}" as id, "{a.value}" as v, {xy} from \'{a.table}\'').fetchnumpy()
    for k, v in t.items():
        if np.ma.isMaskedArray(v) and v.mask.any():
            raise SystemExit(f"{k} has {int(v.mask.sum())} missing values; drop those rows first")
    x, lon, lat = (np.asarray(t[k], float) for k in ("v", "lon", "lat"))
    print(f"units: {len(x)}, value: {a.value}")

    nb = knn_neighbors(lon, lat, a.k)
    g = moran(x, nb, a.permutations, a.seed)
    print(f"global Moran's I, {a.k} nearest neighbours: I {g['I']:.3f} (E[I] {g['EI']:.4f}),"
          f" pseudo p {g['p_sim']:.4f}")

    if a.bands_km:
        print("correlogram (distance band, km: I, pseudo p, units with a neighbour in the band):")
        for lo, hi in zip(a.bands_km[:-1], a.bands_km[1:]):
            bn = band_neighbors(lon, lat, lo, hi)
            r = moran(x, bn, a.permutations, a.seed)
            print(f"  {lo:>7g} - {hi:<7g} I {r['I']:+.3f}  p {r['p_sim']:.4f}  "
                  f"with neighbours {r['n'] - r['islands']}")

    if a.hotspots_out:
        z = getis_ord(x, nb)
        import pyarrow as pa

        hs = pa.table({"id": [str(i) for i in t["id"]], "value": x, "gi_star_z": z})
        con.sql(f"copy (select * from hs order by gi_star_z desc) to '{a.hotspots_out}' (format parquet)")
        print(f"Getis-Ord Gi*, {a.k} nearest neighbours and the unit itself: "
              f"z >= 1.96 in {int((z >= 1.96).sum())} units (hot), z <= -1.96 in {int((z <= -1.96).sum())}"
              " (cold); no correction for multiple tests or for overlapping neighbourhoods")

    if a.local_out:
        lm = local_moran(x, nb, a.permutations, a.seed)
        names = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
        import pyarrow as pa

        lisa = pa.table({
            "id": [str(i) for i in t["id"]],
            "value": x, "lag": lm["lag"] + x.mean(), "local_i": lm["Is"],
            "quadrant": [names[int(v)] for v in lm["q"]], "p_sim": lm["p_sim"],
        })
        con.sql(f"copy (select * from lisa order by id) to '{a.local_out}' (format parquet)")
        sig = lm["p_sim"] <= 0.05
        counts = {names[k]: int(((lm["q"] == k) & sig).sum()) for k in names}
        print(f"local Moran, pseudo p <= 0.05: {counts}, not significant {int((~sig).sum())}"
              " (no correction for multiple tests)")


if __name__ == "__main__":
    main()

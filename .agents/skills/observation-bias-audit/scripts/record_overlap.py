"""Two independently collected records of the same kind of thing (two point lists): which items are in both,
which in one only, and what the overlap says about how many there are if the two records are independent.

    match      one-to-one: pairs closer than --radius, taken shortest first, each point used once
    counts     n1, n2, m (in both); per stratum if --stratum is given (both lists need the column)
    chapman    N = (n1 + 1)(n2 + 1) / (m + 1) - 1, variance (n1 + 1)(n2 + 1)(n1 - m)(n2 - m) / ((m + 1)^2 (m + 2))
               (Chapman 1951, Seber 1970), a 95% interval from it, and each record's completeness n / N

The estimate needs: the same population in both records (the same area and time, the same definition), each
item equally likely to be recorded within a record, and the two records independent. When some items are easy
for both records to catch (big, central, well known) and others hard for both, the overlap is larger than
independence implies and N is too small: read it as a floor, not as the count. Estimating within strata
where detectability is similar removes the part of that dependence that lies between strata.

Matching is part of the estimate: a radius too small misses true pairs (m falls, N rises), a radius too large
pairs different items (m rises, N falls). The script reports N at several radii.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python record_overlap.py A.parquet B.parquet \\
        --x X --y Y --radius 200 [--radii 50 100 200 400] [--stratum COL]
    Coordinates projected (metres); the same column names in both tables.
"""

import argparse

import numpy as np
from scipy.spatial import cKDTree


def match(a, b, radius):
    """Indices (i, j) of one-to-one pairs closer than radius, shortest first."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0:
        return []
    pairs = cKDTree(a).query_ball_tree(cKDTree(b), radius)
    cand = sorted((float(np.hypot(*(a[i] - b[j]))), i, j) for i, js in enumerate(pairs) for j in js)
    used_a, used_b, out = set(), set(), []
    for d, i, j in cand:
        if d < radius and i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            out.append((i, j))
    return out


def chapman(n1, n2, m):
    N = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
    se = np.sqrt(var)
    return {"N": float(N), "se": float(se), "low": float(max(N - 1.96 * se, n1 + n2 - m)), "high": float(N + 1.96 * se),
            "seen": int(n1 + n2 - m), "complete_1": float(n1 / N) if N > 0 else np.nan,
            "complete_2": float(n2 / N) if N > 0 else np.nan}


def overlap(a, b, radius, strata_a=None, strata_b=None):
    """Counts and Chapman estimates, overall and per stratum (matches only within a stratum)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    out = {}
    if strata_a is None:
        m = len(match(a, b, radius))
        out["all"] = {"n1": len(a), "n2": len(b), "m": m, **chapman(len(a), len(b), m)}
        return out
    strata_a, strata_b = np.asarray(strata_a), np.asarray(strata_b)
    total = 0.0
    var = 0.0
    for s in sorted(set(strata_a.tolist()) | set(strata_b.tolist()), key=str):
        ia, ib = strata_a == s, strata_b == s
        m = len(match(a[ia], b[ib], radius))
        c = chapman(int(ia.sum()), int(ib.sum()), m)
        out[s] = {"n1": int(ia.sum()), "n2": int(ib.sum()), "m": m, **c}
        total += c["N"]
        var += c["se"] ** 2
    out["sum of strata"] = {"N": total, "se": float(np.sqrt(var))}
    return out


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--x", required=True)
    p.add_argument("--y", required=True)
    p.add_argument("--radius", type=float, required=True)
    p.add_argument("--radii", type=float, nargs="*", default=[])
    p.add_argument("--stratum")
    a = p.parse_args()
    cols = [a.x, a.y] + ([a.stratum] if a.stratum else [])

    def read(path):
        rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{path}'").fetchall()
        kept = [r for r in rows if r[0] is not None and r[1] is not None]
        return rows, np.array([r[:2] for r in kept], float), (np.array([r[2] for r in kept]) if a.stratum else None)

    ra, A, sa = read(a.a)
    rb, B, sb = read(a.b)
    print(f"record 1: {len(ra)} rows, {len(A)} with coordinates; record 2: {len(rb)} rows, {len(B)} with coordinates")
    res = overlap(A, B, a.radius, sa, sb)
    for k, r in res.items():
        if "n1" in r:
            print(f"  {k}: in 1 {r['n1']}, in 2 {r['n2']}, in both {r['m']}; if independent N {r['N']:.0f} "
                  f"(95% {r['low']:.0f} to {r['high']:.0f}), seen {r['seen']}; completeness 1 {r['complete_1']:.2f}, "
                  f"2 {r['complete_2']:.2f}")
        else:
            print(f"  {k}: N {r['N']:.0f} (se {r['se']:.0f})")
    for rad in a.radii:
        m = len(match(A, B, rad))
        c = chapman(len(A), len(B), m)
        print(f"  radius {rad:g}: in both {m}, N {c['N']:.0f}")
    print("N assumes independent records and equal catchability; items easy for both make it too small (a floor)")


if __name__ == "__main__":
    main()

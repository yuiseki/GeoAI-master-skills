"""Two objectives at once for choosing p sites: the weighted distance (p-median, smaller is better) and the weight
within a radius (coverage, larger is better). They pull towards different sites; no single answer is best for
both. This lists the trade-off.

    epsilon    minimise the weighted distance subject to covering at least eps (a MILP: the p-median model plus
               coverage variables and one constraint); sweeping eps from the coverage optimum down traces every
               Pareto-optimal choice, convex or not
    weighted   minimise distance - lambda x coverage for several lambda (one MILP each): finds only the choices on
               the lower convex hull of the trade-off (supported points); a choice in a dent of the front is never
               found, whatever lambda
    front      the non-dominated (distance, coverage) pairs among a list of choices

The two objectives are on different scales (km x people and people); a weighted sum's lambda has no meaning
until both are written in units the question cares about.

Usage:
    uvx --with numpy --with scipy --with duckdb python pareto.py MATRIX WEIGHTS --p 5 --radius 50 \\
        [--distance sphere_km] [--steps 20]
"""

import argparse

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack


def _value(d, w, open_sites, radius):
    near = d[:, open_sites].min(1)
    return float(np.sum(w * near)), float(np.sum(w * (near <= radius)))


def _model(d, w, p, radius):
    """Variables x_ij (n m), y_j (m), z_i (n). Rows: assign (n), link (n m), count (1), cover (n)."""
    n, m = d.shape
    reach = (d <= radius).astype(float)
    rows = np.repeat(np.arange(n), m)
    assign = hstack([coo_matrix((np.ones(n * m), (rows, np.arange(n * m))), shape=(n, n * m)),
                     csr_matrix((n, m)), csr_matrix((n, n))])
    link = hstack([coo_matrix((np.ones(n * m), (np.arange(n * m), np.arange(n * m)))),
                   coo_matrix((-np.ones(n * m), (np.arange(n * m), np.tile(np.arange(m), n))), shape=(n * m, m)),
                   csr_matrix((n * m, n))])
    count = hstack([csr_matrix((1, n * m)), csr_matrix(np.ones((1, m))), csr_matrix((1, n))])
    cover = hstack([csr_matrix((n, n * m)), csr_matrix(-reach), coo_matrix((np.ones(n), (np.arange(n), np.arange(n))))])
    A = vstack([assign, link, count, cover]).tocsr()
    lb = np.r_[np.ones(n), -np.inf * np.ones(n * m), p, -np.inf * np.ones(n)]
    ub = np.r_[np.ones(n), np.zeros(n * m), p, np.zeros(n)]
    integ = np.r_[np.zeros(n * m), np.ones(m), np.ones(n)]
    return A, lb, ub, integ


def _solve(c, A, lb, ub, integ, n, m):
    res = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=integ, bounds=Bounds(0, 1))
    if res.x is None:
        return None
    return sorted(np.flatnonzero(res.x[n * m:n * m + m] > 0.5).tolist())


def epsilon(d, w, p, radius, eps):
    d, w = np.asarray(d, float), np.asarray(w, float)
    n, m = d.shape
    A, lb, ub, integ = _model(d, w, p, radius)
    cover_row = csr_matrix(np.r_[np.zeros(n * m + m), w][None, :])
    A = vstack([A, cover_row]).tocsr()
    c = np.r_[(w[:, None] * d).ravel(), np.zeros(m + n)]
    return _solve(c, A, np.r_[lb, eps - 1e-9], np.r_[ub, np.inf], integ, n, m)


def weighted(d, w, p, radius, lam):
    d, w = np.asarray(d, float), np.asarray(w, float)
    n, m = d.shape
    A, lb, ub, integ = _model(d, w, p, radius)
    c = np.r_[(w[:, None] * d).ravel(), np.zeros(m), -lam * w]
    return _solve(c, A, lb, ub, integ, n, m)


def front(points):
    """Non-dominated (distance, coverage) pairs: lower distance and higher coverage are better."""
    pts = sorted(set(points), key=lambda t: (t[0], -t[1]))
    out, best_cov = [], -np.inf
    for dist, cov in pts:
        if cov > best_cov:
            out.append((dist, cov))
            best_cov = cov
    return out


def epsilon_front(d, w, p, radius, steps=None):
    """Pareto-optimal (distance, coverage, sites). Exact (steps None): repeat "the largest coverage strictly
    below the last one found, then the least distance that reaches it" until coverage reaches 0; one pair of
    MILPs per distinct level, so only for small problems. steps: instead, eps on that many evenly spaced levels
    between 0 and the largest coverage (an approximation of the front)."""
    d, w = np.asarray(d, float), np.asarray(w, float)
    out = []
    if steps:
        top = _max_cover(d, w, p, radius)
        for eps in np.linspace(top, 0.0, steps):
            o = epsilon(d, w, p, radius, eps)
            if o is not None:
                out.append((*_value(d, w, o, radius), o))
    else:
        cap = np.inf
        while True:
            level = _max_cover(d, w, p, radius, cap)
            if level is None:
                break
            o = epsilon(d, w, p, radius, level)
            dist, cov = _value(d, w, o, radius)
            out.append((dist, cov, o))
            if cov <= 0:
                break
            cap = cov - 1e-9 * max(1.0, cov)
    keep = set(front([(a, b) for a, b, _ in out]))
    seen, res = set(), []
    for a, b, o in out:
        if (a, b) in keep and (a, b) not in seen:
            seen.add((a, b))
            res.append((a, b, o))
    return sorted(res)


def _max_cover(d, w, p, radius, cap=np.inf):
    """The largest coverage <= cap (a MILP over y and z only)."""
    n, m = d.shape
    reach = (d <= radius).astype(float)
    A = vstack([hstack([csr_matrix(-reach), coo_matrix((np.ones(n), (np.arange(n), np.arange(n))))]),
                hstack([csr_matrix(np.ones((1, m))), csr_matrix((1, n))]),
                hstack([csr_matrix((1, m)), csr_matrix(w[None, :])])]).tocsr()
    res = milp(np.r_[np.zeros(m), -w], constraints=LinearConstraint(A, np.r_[-np.inf * np.ones(n), p, -np.inf],
                                                                    np.r_[np.zeros(n), p, cap]),
               integrality=np.ones(m + n), bounds=Bounds(0, 1))
    return None if res.x is None else float(-res.fun)


def main():
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("matrix")
    ap.add_argument("weights")
    ap.add_argument("--p", type=int, required=True)
    ap.add_argument("--radius", type=float, required=True)
    ap.add_argument("--distance", default="network_m")
    ap.add_argument("--steps", type=int, help="approximate the front on this many coverage levels (large problems)")
    a = ap.parse_args()
    rows = duckdb.sql(f"select origin, destination, \"{a.distance}\" from '{a.matrix}'").fetchall()
    origins = sorted({r[0] for r in rows})
    dests = sorted({r[1] for r in rows})
    oi = {x: i for i, x in enumerate(origins)}
    di = {x: j for j, x in enumerate(dests)}
    d = np.full((len(origins), len(dests)), np.nan)
    for o, t, v in rows:
        d[oi[o], di[t]] = v
    if np.isnan(d).any():
        raise SystemExit(f"{int(np.isnan(d).sum())} pairs are missing from the matrix")
    wt = dict(duckdb.sql(f"select cast(id as varchar), weight from '{a.weights}'").fetchall())
    w = np.array([wt[o] for o in origins], float)
    print(f"demand points {len(origins)} (weight {w.sum():.0f}), candidates {len(dests)}, p {a.p}, radius {a.radius:g}")
    pts = epsilon_front(d, w, a.p, a.radius, a.steps)
    print(f"Pareto front by epsilon constraints ({'exact' if not a.steps else f'{a.steps} levels'}): {len(pts)} choices")
    for dist, cov, o in pts:
        print(f"  mean distance {dist / w.sum():.4g}, covered {cov / w.sum():.2%}: {[dests[j] for j in o]}")


if __name__ == "__main__":
    main()

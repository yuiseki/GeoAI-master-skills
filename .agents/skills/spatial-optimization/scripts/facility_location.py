"""Choose p sites from candidates for weighted demand, by MILP and by a heuristic, and check both.

Problems:
    p-median   minimise the weighted sum of each demand point's distance to its nearest open site
    coverage   maximise the weight of demand within --radius of an open site (maximal covering)

Each problem is solved twice: as a MILP (scipy.optimize.milp, i.e. HiGHS) and by a heuristic
(greedy addition then one-for-one swaps for p-median; greedy for coverage). The objective of each
answer is then recomputed from the chosen sites alone. The run stops if a MILP reported as optimal
recomputes worse than the heuristic, or differs from its own reported objective: that is a wrong
model, whatever the solver's status says.

Usage:
    uvx --with numpy --with scipy --with duckdb python facility_location.py MATRIX WEIGHTS \
        --problem p-median|coverage --p 5 [--radius 800] [--distance network_m]

MATRIX: origin (demand id), destination (candidate id), and a distance column, every pair present
(any all-pairs distance table in this shape works). WEIGHTS: id, weight.
"""

import argparse
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack


def pmedian_value(d, w, open_sites):
    return float(np.sum(w * d[:, open_sites].min(axis=1)))


def coverage_value(d, w, open_sites, radius):
    return float(np.sum(w * (d[:, open_sites].min(axis=1) <= radius)))


def pmedian_heuristic(d, w, p):
    n, m = d.shape
    chosen = []
    for _ in range(p):  # greedy: add the site that lowers the total most
        best = min((j for j in range(m) if j not in chosen),
                   key=lambda j: pmedian_value(d, w, chosen + [j]))
        chosen.append(best)
    improved = True
    while improved:  # swap one open site for one closed site while that helps
        improved = False
        cur = pmedian_value(d, w, chosen)
        for i in range(p):
            for j in range(m):
                if j in chosen:
                    continue
                trial = chosen[:i] + [j] + chosen[i + 1:]
                v = pmedian_value(d, w, trial)
                if v < cur - 1e-9:
                    chosen, cur, improved = trial, v, True
    return {"open": sorted(chosen)}


def coverage_heuristic(d, w, p, radius):
    m = d.shape[1]
    chosen = []
    for _ in range(p):
        best = max((j for j in range(m) if j not in chosen),
                   key=lambda j: coverage_value(d, w, chosen + [j], radius))
        chosen.append(best)
    return {"open": sorted(chosen)}


def _status(res):
    return "optimal" if res.status == 0 else f"not optimal ({res.message})"


def pmedian_milp(d, w, p):
    """Variables: x_ij (demand i served by site j), then y_j (site j open)."""
    n, m = d.shape
    c = np.r_[(w[:, None] * d).ravel(), np.zeros(m)]
    rows = np.repeat(np.arange(n), m)
    cols = np.arange(n * m)
    assign = hstack([coo_matrix((np.ones(n * m), (rows, cols)), shape=(n, n * m)),
                     csr_matrix((n, m))])                                    # sum_j x_ij = 1
    link = hstack([coo_matrix((np.ones(n * m), (np.arange(n * m), np.arange(n * m)))),
                   coo_matrix((-np.ones(n * m), (np.arange(n * m), np.tile(np.arange(m), n))),
                              shape=(n * m, m))])                            # x_ij - y_j <= 0
    count = hstack([csr_matrix((1, n * m)), csr_matrix(np.ones((1, m)))])   # sum_j y_j = p
    A = vstack([assign, link, count]).tocsr()
    lb = np.r_[np.ones(n), -np.inf * np.ones(n * m), p]
    ub = np.r_[np.ones(n), np.zeros(n * m), p]
    integrality = np.r_[np.zeros(n * m), np.ones(m)]  # x may stay continuous: y fixes it
    res = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=integrality,
               bounds=Bounds(0, 1))
    if res.x is None:
        return {"status": _status(res), "open": [], "objective": float("nan")}
    y = res.x[n * m:]
    return {"status": _status(res), "open": sorted(np.flatnonzero(y > 0.5).tolist()),
            "objective": float(res.fun)}


def coverage_milp(d, w, p, radius):
    """Variables: y_j (site j open), then z_i (demand i covered); maximise sum w_i z_i."""
    n, m = d.shape
    reach = (d <= radius).astype(float)
    c = np.r_[np.zeros(m), -w]
    cover = hstack([csr_matrix(-reach), coo_matrix((np.ones(n), (np.arange(n), np.arange(n))))])
    count = hstack([csr_matrix(np.ones((1, m))), csr_matrix((1, n))])
    A = vstack([cover, count]).tocsr()
    lb = np.r_[-np.inf * np.ones(n), p]
    ub = np.r_[np.zeros(n), p]
    res = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=np.ones(m + n),
               bounds=Bounds(0, 1))
    if res.x is None:
        return {"status": _status(res), "open": [], "objective": float("nan")}
    return {"status": _status(res), "open": sorted(np.flatnonzero(res.x[:m] > 0.5).tolist()),
            "objective": float(-res.fun)}


def solve(d, w, p, problem_kind="p-median", radius=None):
    d, w = np.asarray(d, float), np.asarray(w, float)
    if problem_kind == "p-median" and np.isinf(d.min(axis=1)).any():
        bad = int(np.isinf(d.min(axis=1)).sum())
        raise SystemExit(f"{bad} demand points cannot reach any candidate; drop or fix them first")
    if problem_kind == "p-median":
        value = lambda o: pmedian_value(d, w, o)  # noqa: E731
        runs = {"milp": lambda: pmedian_milp(d, w, p), "heuristic": lambda: pmedian_heuristic(d, w, p)}
        worse = lambda a, b: a > b + 1e-6 * max(1.0, abs(b))  # noqa: E731
    else:
        value = lambda o: coverage_value(d, w, o, radius)  # noqa: E731
        runs = {"milp": lambda: coverage_milp(d, w, p, radius),
                "heuristic": lambda: coverage_heuristic(d, w, p, radius)}
        worse = lambda a, b: a < b - 1e-6 * max(1.0, abs(b))  # noqa: E731
    out = {}
    for name, run in runs.items():
        t = time.time()
        r = run()
        r["seconds"] = time.time() - t
        if len(r["open"]) != p:
            raise SystemExit(f"{name} opened {len(r['open'])} sites, not {p}: {r.get('status')}")
        r["recomputed"] = value(r["open"])
        out[name] = r
    mi, he = out["milp"], out["heuristic"]
    if mi["status"] == "optimal":
        if abs(mi["recomputed"] - mi["objective"]) > 1e-6 * max(1.0, abs(mi["objective"])):
            raise SystemExit(f"MILP reports {mi['objective']} but its sites give {mi['recomputed']}:"
                             " the model is wrong")
        if worse(mi["recomputed"], he["recomputed"]):
            raise SystemExit(f"an 'optimal' MILP ({mi['recomputed']}) is worse than the heuristic "
                             f"({he['recomputed']}): the model is wrong")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("matrix")
    p.add_argument("weights")
    p.add_argument("--problem", choices=["p-median", "coverage"], required=True)
    p.add_argument("--p", type=int, nargs="+", required=True)
    p.add_argument("--radius", type=float)
    p.add_argument("--distance", default="network_m")
    a = p.parse_args()
    if a.problem == "coverage" and a.radius is None:
        p.error("coverage needs --radius")

    import duckdb

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
    missing = [o for o in origins if o not in wt]
    if missing:
        raise SystemExit(f"{len(missing)} demand points have no weight, e.g. {missing[:3]}")
    w = np.array([wt[o] for o in origins], float)
    print(f"demand points {len(origins)} (weight {w.sum():.0f}), candidates {len(dests)}, "
          f"distance: {a.distance}")
    for k in a.p:
        out = solve(d, w, k, a.problem, a.radius)
        mi, he = out["milp"], out["heuristic"]
        unit = "weighted m" if a.problem == "p-median" else f"weight within {a.radius:g} m"
        print(f"p={k}: MILP {mi['status']} {mi['recomputed']:.6g} {unit} ({mi['seconds']:.1f}s), "
              f"heuristic {he['recomputed']:.6g} ({he['seconds']:.1f}s)")
        if a.problem == "p-median":
            print(f"    mean distance per unit of weight: {mi['recomputed'] / w.sum():.1f} m")
        else:
            print(f"    share of weight covered: {mi['recomputed'] / w.sum():.1%}")
        print(f"    open: {[dests[j] for j in mi['open']]}")


if __name__ == "__main__":
    main()

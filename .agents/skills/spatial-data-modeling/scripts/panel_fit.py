"""Linear regression on a panel (the same units observed at several times), with unit and time effects
and standard errors clustered by unit.

    effects   none     pooled OLS with an intercept: every row treated as a separate observation
              unit     unit fixed effects: only change within a unit over time identifies the slope
              time     time fixed effects: only differences between units in the same period
              twoway   both (alternating demeaning, so unbalanced panels work)
A regressor with no variation left after the effects (an area or a region code under unit effects) cannot
be estimated; it is listed in dropped and its coefficient is NaN, rather than given a number.

se_naive assumes independent rows; se_cluster (CR1: G / (G - 1) x (n - 1) / (n - k) on the sandwich, k the
regressors kept) allows any correlation within a cluster and none between clusters. Errors shared by
neighbouring units in the same year are correlation between clusters: cluster by a coarser unit (region)
or check with time effects.

decompose splits a variable's variance into between units (the spread of unit means) and within units
(deviations from the unit's own mean). lag takes the value of the same unit exactly k periods earlier,
never a later one, and NaN where that period is missing; two rows for one unit and period stop it.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python panel_fit.py TABLE UNIT TIME TARGET F1 [F2 ...] \\
        --effects none unit time twoway [--cluster COLUMN]
"""

import argparse

import numpy as np

EFFECTS = ("none", "unit", "time", "twoway")


def _demean(a, codes):
    out = a.copy()
    for g in np.unique(codes):
        m = codes == g
        out[m] -= out[m].mean(axis=0)
    return out


def _absorb(a, unit, time, effects, tol=1e-13, max_iter=10_000):
    if effects == "unit":
        return _demean(a, unit)
    if effects == "time":
        return _demean(a, time)
    out = a.copy()
    for _ in range(max_iter):
        new = _demean(_demean(out, unit), time)
        if np.max(np.abs(new - out)) < tol * (1 + np.max(np.abs(a))):
            return new
        out = new
    raise RuntimeError("two-way demeaning did not converge")


def fit(y, X, unit, time, effects="none", cluster=None, names=None, intercept=True):
    if effects not in EFFECTS:
        raise ValueError(f"effects must be one of {EFFECTS}")
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    names = list(names) if names is not None else [f"x{j}" for j in range(X.shape[1])]
    unit, time = np.asarray(unit), np.asarray(time)
    if effects == "none":
        Xw, yw = X, y
        absorbed = 0
    else:
        Z = _absorb(np.c_[y, X], unit, time, effects)
        yw, Xw = Z[:, 0], Z[:, 1:]
        absorbed = {"unit": len(np.unique(unit)), "time": len(np.unique(time)),
                    "twoway": len(np.unique(unit)) + len(np.unique(time)) - 1}[effects]
    scale = np.abs(X).max(axis=0) + 1
    keep = Xw.std(axis=0) > 1e-9 * scale
    dropped = [n for n, k in zip(names, keep) if not k]
    D = Xw[:, keep]
    if effects == "none" and intercept:
        D = np.c_[np.ones(len(y)), D]
    n, k = D.shape
    XtX_inv = np.linalg.inv(D.T @ D)
    b = XtX_inv @ D.T @ yw
    u = yw - D @ b
    dof = n - k - absorbed
    se_naive = np.sqrt(np.diag(XtX_inv) * (u @ u) / dof)
    off = 1 if effects == "none" and intercept else 0
    out = {"names": names, "coef": np.full(len(names), np.nan), "se_naive": np.full(len(names), np.nan),
           "dropped": dropped, "n": n, "dof": dof}
    out["coef"][keep] = b[off:]
    out["se_naive"][keep] = se_naive[off:]
    if cluster is not None:
        cluster = np.asarray(cluster)
        groups = np.unique(cluster)
        G = len(groups)
        meat = np.zeros((k, k))
        for g in groups:
            s = D[cluster == g].T @ u[cluster == g]
            meat += np.outer(s, s)
        V = G / (G - 1) * (n - 1) / (n - k) * XtX_inv @ meat @ XtX_inv
        out["se_cluster"] = np.full(len(names), np.nan)
        out["se_cluster"][keep] = np.sqrt(np.diag(V))[off:]
        out["clusters"] = G
    return out


def decompose(v, unit):
    v = np.asarray(v, float)
    unit = np.asarray(unit)
    means = np.zeros_like(v)
    for g in np.unique(unit):
        means[unit == g] = v[unit == g].mean()
    between = float(np.mean((means - v.mean()) ** 2))
    within = float(np.mean((v - means) ** 2))
    return {"between_var": between, "within_var": within, "within_share": within / (between + within)}


def lag(v, unit, time, k=1):
    v = np.asarray(v, float)
    at = {}
    for u, t, x in zip(np.asarray(unit).tolist(), np.asarray(time).tolist(), v):
        if (u, t) in at:
            raise ValueError(f"unit {u!r} has two rows for period {t!r}")
        at[(u, t)] = x
    return np.array([at.get((u, t - k), np.nan) for u, t in zip(np.asarray(unit).tolist(),
                                                                  np.asarray(time).tolist())])


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("unit")
    p.add_argument("time")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--effects", nargs="+", default=list(EFFECTS), choices=EFFECTS)
    p.add_argument("--cluster", help="column to cluster the standard errors by (default: the unit)")
    a = p.parse_args()
    cols = [a.unit, a.time, a.target, *a.features] + ([a.cluster] if a.cluster else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; drop them first")
    unit = np.array([r[0] for r in kept])
    time = np.array([r[1] for r in kept])
    y = np.array([r[2] for r in kept], float)
    X = np.array([r[3:3 + len(a.features)] for r in kept], float)
    cl = np.array([r[-1] for r in kept]) if a.cluster else unit
    print(f"rows {len(y)}, units {len(np.unique(unit))}, periods {len(np.unique(time))}, "
          f"clusters {len(np.unique(cl))} ({a.cluster or a.unit})")
    for name, col in [(a.target, y)] + list(zip(a.features, X.T)):
        d = decompose(col, unit)
        print(f"  {name}: within-unit share of variance {d['within_share']:.3f}")
    for e in a.effects:
        r = fit(y, X, unit, time, e, cluster=cl, names=a.features)
        for j, n in enumerate(a.features):
            print(f"{e:<7} {n}: coef {r['coef'][j]:.4g}  se naive {r['se_naive'][j]:.3g}  "
                  f"se clustered {r['se_cluster'][j]:.3g}")
        if r["dropped"]:
            print(f"{e:<7} not estimable (no variation left): {', '.join(r['dropped'])}")


if __name__ == "__main__":
    main()

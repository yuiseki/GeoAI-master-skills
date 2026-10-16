"""Spatial lag and spatial error regressions by maximum likelihood, with the Lagrange multiplier tests that
point between them and the direct and indirect effects of the lag model.

    lag    y = rho W y + X beta + e. The outcome depends on the neighbours' outcomes: a change in x at one
           unit spreads to the others through rho. A coefficient is not the effect of x; the impacts are:
           direct (average own effect, including feedback), total (beta / (1 - rho) with row-standardised
           W), indirect (total - direct)
    error  y = X beta + u, u = lambda W u + e. Unmeasured, spatially patterned factors in the error;
           beta keeps its OLS meaning, only the efficiency and standard errors change
    LM     from the OLS residuals: LM-lag, LM-error and their robust forms (Anselin and others 1996), chi^2(1)

Maximum likelihood concentrates beta and sigma^2 out and maximises over rho (or lambda) on the interval
(1 / smallest eigenvalue of W, 1), using the eigenvalues for log|I - rho W|. Standard errors come from the
asymptotic information matrix. W must be row-standardised (rows of units without neighbours stay zero) and
is held dense: up to 3,000 units.

W comes from a pair table (id, neighbour; both directions) or k nearest neighbours on the sphere.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python spatial_regression.py TABLE ID TARGET X1 [...] \\
        (--pairs PAIRS | --knn K --lon LON --lat LAT)
"""

import argparse

import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar

MAX_UNITS = 3000


def rook_weights(side):
    n = side * side
    W = np.zeros((n, n))
    for r in range(side):
        for c in range(side):
            for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= rr < side and 0 <= cc < side:
                    W[r * side + c, rr * side + cc] = 1
    return W / W.sum(1, keepdims=True)


def _row_standardise(B):
    s = B.sum(1, keepdims=True)
    return np.divide(B, s, out=np.zeros_like(B), where=s > 0)


def lm_tests(y, X, W):
    y, X = np.asarray(y, float), np.asarray(X, float)
    n = len(y)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    s2 = e @ e / n
    T = np.trace(W.T @ W + W @ W)
    WXb = W @ (X @ b)
    M_WXb = WXb - X @ np.linalg.lstsq(X, WXb, rcond=None)[0]
    D = (WXb @ M_WXb + T * s2) / s2
    d_lag, d_err = e @ (W @ y) / s2, e @ (W @ e) / s2
    stat = {"lm_lag": d_lag ** 2 / D, "lm_error": d_err ** 2 / T,
            "rlm_lag": (d_lag - d_err) ** 2 / (D - T), "rlm_error": (d_err - T / D * d_lag) ** 2 / (T * (1 - T / D))}
    return {k: (float(v), float(stats.chi2.sf(v, 1))) for k, v in stat.items()}


def _bounds(W):
    lam = np.linalg.eigvals(W).real
    return lam, (1 / lam.min() + 1e-6, 1 - 1e-6)


def ml_lag(y, X, W):
    y, X = np.asarray(y, float), np.asarray(X, float)
    n = len(y)
    if n > MAX_UNITS:
        raise SystemExit(f"{n} units; this script holds W dense, up to {MAX_UNITS}")
    lam, bounds = _bounds(W)
    Wy = W @ y
    XtX_inv_Xt = np.linalg.pinv(X)

    def negll(rho):
        Ay = y - rho * Wy
        e = Ay - X @ (XtX_inv_Xt @ Ay)
        s2 = e @ e / n
        return -(np.log(1 - rho * lam).sum() - n / 2 * np.log(2 * np.pi * s2) - n / 2)

    rho = minimize_scalar(negll, bounds=bounds, method="bounded", options={"xatol": 1e-10}).x
    Ay = y - rho * Wy
    beta = XtX_inv_Xt @ Ay
    e = Ay - X @ beta
    s2 = e @ e / n
    A_inv = np.linalg.inv(np.eye(n) - rho * W)
    WA = W @ A_inv
    WAXb = WA @ (X @ beta)
    k = X.shape[1]
    info = np.zeros((k + 2, k + 2))
    info[:k, :k] = X.T @ X / s2
    info[:k, k] = info[k, :k] = X.T @ WAXb / s2
    info[k, k] = np.trace(WA @ WA) + np.trace(WA.T @ WA) + WAXb @ WAXb / s2
    info[k, k + 1] = info[k + 1, k] = np.trace(WA) / s2
    info[k + 1, k + 1] = n / (2 * s2 ** 2)
    V = np.linalg.inv(info)
    return {"rho": float(rho), "beta": beta, "sigma2": float(s2), "se_beta": np.sqrt(np.diag(V)[:k]),
            "se_rho": float(np.sqrt(V[k, k])), "loglik": float(-negll(rho)), "k": k + 2}


def ml_error(y, X, W):
    y, X = np.asarray(y, float), np.asarray(X, float)
    n = len(y)
    if n > MAX_UNITS:
        raise SystemExit(f"{n} units; this script holds W dense, up to {MAX_UNITS}")
    lam, bounds = _bounds(W)
    Wy, WX = W @ y, W @ X

    def fit(l):
        ys, Xs = y - l * Wy, X - l * WX
        b = np.linalg.lstsq(Xs, ys, rcond=None)[0]
        e = ys - Xs @ b
        return b, e @ e / n

    def negll(l):
        _, s2 = fit(l)
        return -(np.log(1 - l * lam).sum() - n / 2 * np.log(2 * np.pi * s2) - n / 2)

    l = minimize_scalar(negll, bounds=bounds, method="bounded", options={"xatol": 1e-10}).x
    beta, s2 = fit(l)
    Xs = X - l * WX
    B_inv = np.linalg.inv(np.eye(n) - l * W)
    WB = W @ B_inv
    V_beta = np.linalg.inv(Xs.T @ Xs / s2)
    info = np.array([[np.trace(WB @ WB) + np.trace(WB.T @ WB), np.trace(WB) / s2],
                     [np.trace(WB) / s2, n / (2 * s2 ** 2)]])
    V = np.linalg.inv(info)
    return {"lambda": float(l), "beta": beta, "sigma2": float(s2), "se_beta": np.sqrt(np.diag(V_beta)),
            "se_lambda": float(np.sqrt(V[0, 0])), "loglik": float(-negll(l)), "k": X.shape[1] + 2}


def impacts(rho, beta, W):
    """Average direct, indirect and total impacts of each coefficient in a lag model."""
    n = W.shape[0]
    A_inv = np.linalg.inv(np.eye(n) - rho * W)
    d = np.trace(A_inv) / n
    t = A_inv.sum() / n
    beta = np.asarray(beta, float)
    return {"direct": beta * d, "total": beta * t, "indirect": beta * (t - d)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--pairs", help="a table (id, neighbour), both directions")
    p.add_argument("--knn", type=int)
    p.add_argument("--lon")
    p.add_argument("--lat")
    a = p.parse_args()

    import duckdb

    cols = [a.id, a.target, *a.features] + ([a.lon, a.lat] if a.knn else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("missing values in the columns used; drop those rows (and their neighbour pairs) first")
    ids = [str(r[0]) for r in rows]
    index = {u: i for i, u in enumerate(ids)}
    n = len(ids)
    y = np.array([r[1] for r in rows], float)
    X = np.c_[np.ones(n), np.array([r[2:2 + len(a.features)] for r in rows], float)]
    B = np.zeros((n, n))
    if a.pairs:
        unknown = 0
        for u, v in duckdb.sql(f"select id, neighbour from '{a.pairs}'").fetchall():
            if str(u) in index and str(v) in index:
                B[index[str(u)], index[str(v)]] = 1
            else:
                unknown += 1
        print(f"neighbour pairs with unknown ids: {unknown}")
    elif a.knn:
        lon, lat = np.radians([r[-2] for r in rows]), np.radians([r[-1] for r in rows])
        h = (np.sin((lat[:, None] - lat[None]) / 2) ** 2
             + np.cos(lat[:, None]) * np.cos(lat[None]) * np.sin((lon[:, None] - lon[None]) / 2) ** 2)
        D = 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1))) + np.diag(np.full(n, np.inf))
        for i, js in enumerate(np.argsort(D, 1)[:, :a.knn]):
            B[i, js] = 1
    else:
        p.error("give --pairs or --knn with --lon and --lat")
    W = _row_standardise(B)
    print(f"units {n}, islands {int((B.sum(1) == 0).sum())}, neighbours per unit median {np.median(B.sum(1)):g}; "
          "W row-standardised")
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    print("OLS: " + ", ".join(f"{nme} {b:.5g}" for nme, b in zip(["const", *a.features], ols)))
    for k, (s, pv) in lm_tests(y, X, W).items():
        print(f"  {k}: {s:.4g} (p {pv:.3g})")
    lag, err = ml_lag(y, X, W), ml_error(y, X, W)
    print(f"ML lag: rho {lag['rho']:.5g} (se {lag['se_rho']:.3g}), log-likelihood {lag['loglik']:.6g}, "
          f"AIC {2 * lag['k'] - 2 * lag['loglik']:.6g}")
    imp = impacts(lag["rho"], lag["beta"][1:], W)
    for j, nme in enumerate(a.features):
        print(f"  {nme}: beta {lag['beta'][j + 1]:.5g} (se {lag['se_beta'][j + 1]:.3g}); impacts direct "
              f"{imp['direct'][j]:.5g}, indirect {imp['indirect'][j]:.5g}, total {imp['total'][j]:.5g}")
    print(f"ML error: lambda {err['lambda']:.5g} (se {err['se_lambda']:.3g}), log-likelihood {err['loglik']:.6g}, "
          f"AIC {2 * err['k'] - 2 * err['loglik']:.6g}")
    for j, nme in enumerate(a.features):
        print(f"  {nme}: beta {err['beta'][j + 1]:.5g} (se {err['se_beta'][j + 1]:.3g})")


if __name__ == "__main__":
    main()

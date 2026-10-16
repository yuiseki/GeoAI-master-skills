"""Geographically weighted regression: a weighted least-squares fit at every unit, with weights falling with
distance, to see whether coefficients change across space.

    kernel     bisquare (zero beyond the bandwidth) or gaussian; adaptive (the bandwidth is the distance to the
               bw-th nearest unit, the unit itself counted) or fixed (a distance)
    bandwidth  chosen by the smallest AICc: a coarse profile over candidate bandwidths, then a golden-section
               search around its minimum (adaptive bandwidths are integers). The profile is printed; AICc can
               have more than one dip
    output     local coefficients, standard errors and t values; tr(S), the effective number of parameters;
               AICc; the critical t adjusted for testing at every unit (da Silva and Fotheringham 2016: alpha
               times the number of coefficients over tr(S)); local collinearity (local_collinearity: condition
               numbers, VIFs, variance-decomposition proportions)

Local coefficients vary for reasons other than a varying process: chance (they are noisy where the bandwidth is
small), correlated predictors (two local slopes trade off against each other), and a missing variable that
varies in space. A map of local coefficients is a description, to be read with these in mind.

Distances are Euclidean on --x/--y in a projected CRS (metres), or great-circle km on --lon/--lat.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python gwr.py TABLE ID TARGET X1 [...] \\
        (--x X --y Y | --lon LON --lat LAT) [--kernel bisquare|gaussian] [--fixed] [--bw B] [--out local.csv]
"""

import argparse
import math

import numpy as np
from scipy import stats

EARTH_KM = 6371.0


def _distances(coords, spherical=False):
    c = np.asarray(coords, float)
    if spherical:
        lo, la = np.radians(c[:, 0]), np.radians(c[:, 1])
        h = (np.sin((la[:, None] - la[None]) / 2) ** 2
             + np.cos(la[:, None]) * np.cos(la[None]) * np.sin((lo[:, None] - lo[None]) / 2) ** 2)
        return 2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
    return np.sqrt(((c[:, None, :] - c[None, :, :]) ** 2).sum(-1))


def _weights(d, bw, kernel, fixed):
    h = float(bw) if fixed else np.partition(d, int(bw) - 1)[int(bw) - 1] * 1.0000001
    z = d / h
    if kernel == "bisquare":
        w = (1 - z ** 2) ** 2
        w[d >= h] = 0
        return w
    if kernel == "gaussian":
        return np.exp(-0.5 * z ** 2)
    raise SystemExit(f"unknown kernel {kernel}")


def gwr(coords, y, X, bw, kernel="bisquare", fixed=False, spherical=False, D=None):
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    D = _distances(coords, spherical) if D is None else D
    params, cct, s_diag = np.empty((n, k)), np.empty((n, k)), np.empty(n)
    for i in range(n):
        w = _weights(D[i], bw, kernel, fixed)
        XtW = X.T * w
        A = XtW @ X
        try:
            C = np.linalg.solve(A, XtW)  # k x n
        except np.linalg.LinAlgError:
            raise SystemExit(f"the local fit at unit {i} is singular: widen the bandwidth")
        params[i] = C @ y
        s_diag[i] = X[i] @ C[:, i]
        cct[i] = (C * C).sum(1)
    yhat = (X * params).sum(1)
    resid = y - yhat
    tr_S = float(s_diag.sum())
    rss = float(resid @ resid)
    sigma2 = rss / (n - tr_S)
    bse = np.sqrt(cct * sigma2)
    adj = 0.05 * k / tr_S
    return {"params": params, "bse": bse, "tvalues": params / bse, "resid": resid, "tr_S": tr_S, "rss": rss,
            "n": n, "k": k, "bw": bw, "critical_t": float(stats.t.ppf(1 - adj / 2, n - 1)), "adj_alpha": adj}


def local_collinearity(coords, X, bw, kernel="bisquare", fixed=False, spherical=False, D=None, root=True):
    """Wheeler (2007)'s local diagnostics of the weighted design at every unit. X includes the constant first.

    correlation  weighted correlations of the slopes' columns, pairs (j, k) with 1 <= j < k
    vif          local variance inflation factors of the slopes (the diagonal of the inverse correlation)
    condition    local condition number: the largest over the smallest singular value of the weighted design,
                 each column scaled to unit length. root=True weights rows by sqrt(w) (W^(1/2) X, the matrix
                 whose cross-product the local fit inverts); root=False by w, as mgwr 2.2 does
    vdp          variance-decomposition proportions of the smallest singular value, one per column: two or more
                 large (above 0.5) with a large condition number mark the columns that are collinear"""
    X = np.asarray(X, float)
    n, k = X.shape
    D = _distances(coords, spherical) if D is None else D
    pairs = [(j, m) for j in range(1, k) for m in range(j + 1, k)]
    corr = np.empty((n, len(pairs)))
    vif = np.empty((n, k - 1))
    cond = np.empty(n)
    vdp = np.empty((n, k))
    for i in range(n):
        w = _weights(D[i], bw, kernel, fixed)
        w = w / w.sum()
        C = np.cov(X[:, 1:].T, aweights=w).reshape(k - 1, k - 1)
        sd = np.sqrt(np.diag(C))
        R = C / np.outer(sd, sd)
        corr[i] = [R[j - 1, m - 1] for j, m in pairs]
        vif[i] = np.diag(np.linalg.inv(R)) if k > 2 else 1.0
        Z = X * (np.sqrt(w) if root else w)[:, None]
        Z = Z / np.sqrt((Z ** 2).sum(0))
        _, sv, vt = np.linalg.svd(Z, full_matrices=False)
        cond[i] = sv[0] / sv[-1]
        phi = (vt.T / sv) ** 2  # k x k: column j, singular value l
        vdp[i] = phi[:, -1] / phi.sum(1)
    return {"pairs": pairs, "correlation": corr, "vif": vif, "condition": cond, "vdp": vdp}


def aicc(r):
    n, k = r["n"], r["tr_S"]
    llf = -n / 2 * (1 + math.log(2 * math.pi * r["rss"] / n))
    return -2 * llf + 2 * n * (k + 1) / (n - k - 2)


def select_bandwidth(coords, y, X, kernel="bisquare", fixed=False, spherical=False, candidates=25):
    D = _distances(coords, spherical)
    n, k = np.asarray(X).shape
    if fixed:
        lo, hi = np.partition(D, 1, axis=1)[:, 1].max() * 1.01, D.max()
        grid = np.geomspace(lo, hi, candidates)
    else:
        lo, hi = k + 2, n
        grid = np.unique(np.geomspace(lo, hi, candidates).round().astype(int))

    def score(b):
        try:
            r = gwr(coords, y, X, b, kernel, fixed, spherical, D)
        except SystemExit:
            return np.inf
        return aicc(r) if r["n"] - r["tr_S"] - 2 > 0 else np.inf

    profile = [(float(b), score(b)) for b in grid]
    j = int(np.argmin([s for _, s in profile]))
    a, b = profile[max(j - 1, 0)][0], profile[min(j + 1, len(profile) - 1)][0]
    cache = {}

    def f(x):
        x = x if fixed else int(round(x))
        if x not in cache:
            cache[x] = score(x)
        return cache[x]

    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    while (b - a) > (1e-6 * max(1.0, b) if fixed else 1):
        if f(c) < f(d):
            b = d
        else:
            a = c
        c, d = b - g * (b - a), a + g * (b - a)
    cand = [x for x in ([a, b, c, d] if fixed else range(int(math.floor(a)), int(math.ceil(b)) + 1))]
    best = min(cand + [profile[j][0]], key=f)
    return {"bw": best if fixed else int(round(best)), "aicc": f(best), "profile": profile}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--x")
    p.add_argument("--y")
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--kernel", choices=["bisquare", "gaussian"], default="bisquare")
    p.add_argument("--fixed", action="store_true")
    p.add_argument("--bw", type=float)
    p.add_argument("--standardise", action="store_true", help="standardise the features (comparable slopes)")
    p.add_argument("--out")
    a = p.parse_args()
    if not ((a.x and a.y) or (a.lon and a.lat)):
        p.error("give --x/--y (projected, metres) or --lon/--lat")

    import duckdb

    cc = [a.x, a.y] if a.x else [a.lon, a.lat]
    cols = [a.id, a.target, *a.features, *cc]
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("missing values in the columns used; drop those rows first")
    n, kf = len(rows), len(a.features)
    y = np.array([r[1] for r in rows], float)
    F = np.array([r[2:2 + kf] for r in rows], float)
    if a.standardise:
        F = (F - F.mean(0)) / F.std(0)
    X = np.c_[np.ones(n), F]
    coords = np.array([r[-2:] for r in rows], float)
    sph = bool(a.lon)
    print(f"units {n}, distances {'great-circle km' if sph else 'Euclidean in the CRS units'}, kernel {a.kernel} "
          f"{'fixed' if a.fixed else 'adaptive (neighbours)'}")
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    rss0 = ((y - X @ ols) ** 2).sum()
    k0 = X.shape[1]
    aicc0 = n * math.log(rss0 / n) + n * math.log(2 * math.pi) + n * (n + k0) / (n - k0 - 2)
    if a.bw:
        bw = a.bw if a.fixed else int(a.bw)
    else:
        sel = select_bandwidth(coords, y, X, a.kernel, a.fixed, sph)
        bw = sel["bw"]
        print("AICc profile: " + ", ".join(f"{b:g} {s:.1f}" for b, s in sel["profile"]))
    r = gwr(coords, y, X, bw, a.kernel, a.fixed, sph)
    print(f"bandwidth {bw:g}, tr(S) {r['tr_S']:.2f}, AICc {aicc(r):.2f} (global OLS {aicc0:.2f}); adjusted alpha "
          f"{r['adj_alpha']:.4f}, critical |t| {r['critical_t']:.3f}")
    for j, nme in enumerate(["const", *a.features]):
        q = np.quantile(r["params"][:, j], [0, 0.25, 0.5, 0.75, 1])
        sig = int((np.abs(r["tvalues"][:, j]) > r["critical_t"]).sum())
        print(f"  {nme}: global {ols[j]:.4g}; local min {q[0]:.4g}, q1 {q[1]:.4g}, median {q[2]:.4g}, q3 {q[3]:.4g}, "
              f"max {q[4]:.4g}; units beyond the adjusted |t| {sig} of {n}")
    lc = local_collinearity(coords, X, bw, a.kernel, a.fixed, sph)
    cn = lc["condition"]
    print(f"local condition number (W^1/2 X, columns scaled): median {np.median(cn):.3g}, max {cn.max():.3g}; "
          f"units above 30: {int((cn > 30).sum())}, above 10: {int((cn > 10).sum())} of {n}")
    if kf >= 1:
        vmax = lc["vif"].max(0)
        print("  largest local VIF per feature: " + ", ".join(f"{f} {v:.3g}" for f, v in zip(a.features, vmax)))
    if (cn > 30).any():
        print("  where the condition number is above 30, local slopes there trade off against each other: do not map "
              "them as spatial variation (variance-decomposition proportions in --out say which columns)")
    if kf >= 2:
        cm = np.corrcoef(r["params"][:, 1:].T)
        print("correlation of local slopes (strongly negative pairs may be collinearity, not spatial variation):")
        for i in range(kf):
            for j in range(i + 1, kf):
                print(f"  {a.features[i]} / {a.features[j]}: {cm[i, j]:+.2f}")
    if a.out:
        with open(a.out, "w") as f:
            names = ["const", *a.features]
            f.write("id," + ",".join(f"b_{c},se_{c},t_{c}" for c in names) + ",condition,"
                    + ",".join(f"vdp_{c}" for c in names) + "\n")
            for i, row in enumerate(rows):
                f.write(str(row[0]) + "," + ",".join(f"{r['params'][i, j]},{r['bse'][i, j]},{r['tvalues'][i, j]}"
                                                     for j in range(X.shape[1]))
                        + f",{cn[i]}," + ",".join(str(v) for v in lc["vdp"][i]) + "\n")
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

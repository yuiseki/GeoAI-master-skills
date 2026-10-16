"""Space-time kriging with a separable covariance, fitted by maximum likelihood.

    C((s, t), (s', t')) = sill * fs(|s - s'| / range_s) * ft(|t - t'| / range_t)  [+ nugget on the same observation]

fs and ft are exponential (exp(-r)) or Gaussian (exp(-r^2)). An exponential ft at whole time steps is an AR(1)
in time with phi = exp(-1 / range_t). The mean is an unknown constant, estimated by generalised least squares
(ordinary kriging) and profiled out of the likelihood; mean="zero" uses a known mean of 0 (simple kriging).
This is Gaussian-process regression with a product kernel.

    covariance      the matrix between two sets of (x, y, t)
    loglik / fit    Gaussian log-likelihood; fit maximises it over log(sill, range_s, range_t, nugget)
    predict         the kriging mean and variance at new (x, y, t): the variance of the latent value, and of a
                    new observation (plus the nugget)
    variogram       the empirical space-time semivariogram: half the mean squared difference of pairs, by
                    distance band and time lag, to set beside the fitted model's

Separable means the correlation in space does not depend on the time lag and the other way round. A field
that moves (wind, a river, a front) is not separable: the best predictor of a place's future is upstream, and
the separable model cannot point there. The covariance is held as an n x n matrix: up to about 3,000
observations.

Usage (the mean structure first, then kriging of the residuals, scored on the prediction targets):
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python st_kriging.py TABLE LOCATION TIME X Y VALUE \\
        --cutoff T [--detrend time|additive|none] [--space exponential|gaussian] [--time exponential|gaussian] \\
        [--blocks] [--alpha 0.1]
    --detrend time (default) removes mu + b(t); additive also removes a(s), whose error at a new location is
    left out of the interval (see detrend_and_krige).
"""

import argparse

import numpy as np
from scipy import linalg, optimize, stats

FAMILIES = {"exponential": lambda r: np.exp(-r), "gaussian": lambda r: np.exp(-r * r)}


def lags(A, B):
    """Distances in space and in time between the rows of A (n, 3) and B (m, 3): x, y, t."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    h = np.sqrt((A[:, None, 0] - B[None, :, 0]) ** 2 + (A[:, None, 1] - B[None, :, 1]) ** 2)
    return h, np.abs(A[:, None, 2] - B[None, :, 2])


def covariance(params, A, B, space="exponential", time="exponential", hu=None):
    """A, B: arrays (n, 3) and (m, 3) of x, y, t. params: sill, range_s, range_t (the nugget is not added).
    hu: the lags, if already computed."""
    sill, rs, rt = params[:3]
    h, u = hu if hu is not None else lags(A, B)
    return sill * FAMILIES[space](h / rs) * FAMILIES[time](u / rt)


def _solve_parts(params, P, y, space, time, mean, hu=None):
    sill, rs, rt, nugget = params
    K = covariance(params, P, P, space, time, hu) + (nugget + 1e-10 * sill) * np.eye(len(y))
    cf = linalg.cho_factor(K, lower=True)
    one = np.ones(len(y))
    if mean == "zero":
        beta = 0.0
    else:
        Ki1 = linalg.cho_solve(cf, one)
        beta = float(Ki1 @ y / (one @ Ki1))
    r = y - beta
    alpha = linalg.cho_solve(cf, r)
    return cf, beta, r, alpha


def loglik(params, P, y, space="exponential", time="exponential", mean="constant", hu=None):
    """The log-likelihood with the constant mean at its GLS estimate (a profile likelihood)."""
    y = np.asarray(y, float)
    try:
        cf, beta, r, alpha = _solve_parts(params, P, y, space, time, mean, hu)
    except linalg.LinAlgError:
        return -np.inf
    logdet = 2 * np.log(np.diag(cf[0])).sum()
    return float(-0.5 * (r @ alpha + logdet + len(y) * np.log(2 * np.pi)))


def fit(P, y, space="exponential", time="exponential", mean="constant", start=None):
    P, y = np.asarray(P, float), np.asarray(y, float)
    if len(y) > 3000:
        raise SystemExit(f"{len(y)} observations; the n x n covariance is held in memory, up to 3,000")
    v = y.var()
    span_s = np.ptp(P[:, :2], axis=0).max()
    span_t = max(np.ptp(P[:, 2]), 1.0)
    z0 = np.log(start) if start is not None else np.log([0.7 * v, span_s / 5, span_t / 5, 0.3 * v])

    hu = lags(P, P)

    def neg(z):
        val = loglik(np.exp(z), P, y, space, time, mean, hu)
        return -val if np.isfinite(val) else 1e300

    # Bounded in log space so that a range cannot run off to where the matrix is numerically singular.
    lo = np.log([1e-6 * v, 1e-3 * span_s, 1e-3 * span_t, 1e-8 * v])
    hi = np.log([100 * v, 100 * span_s, 100 * span_t, 100 * v])
    # The likelihood has several modes in the ranges (a short and a very long range in time can both fit).
    # Score a coarse grid of ranges first and start from the three best points.
    starts = [z0] if start is not None else []
    if start is None:
        grid = []
        for rs in span_s * np.array([0.02, 0.07, 0.25, 1.0, 4.0]):
            for rt in span_t * np.array([0.02, 0.07, 0.25, 1.0, 4.0]):
                for share in (0.3, 0.8):
                    z = np.log([share * v, rs, rt, (1 - share) * v])
                    grid.append((neg(z), tuple(z)))
        starts = [np.array(z) for _, z in sorted(grid)[:3]]
    best = None
    for z in starts:
        r = optimize.minimize(neg, np.clip(z, lo, hi), method="L-BFGS-B", bounds=list(zip(lo, hi)),
                              options={"ftol": 1e-12, "gtol": 1e-6})
        if best is None or r.fun < best.fun:
            best = r
    params = np.exp(best.x)
    return {"params": params, "loglik": -best.fun, "space": space, "time": time, "mean": mean,
            "at_edge": bool(params[1] > 20 * span_s or params[2] > 20 * span_t or params[3] < 1e-6 * v)}


def predict(model, P, y, Q):
    """Kriging at Q (m, 3) from observations P, y. Returns mean, variance of the latent value, variance of a new
    observation."""
    params, space, time, mean = model["params"], model["space"], model["time"], model["mean"]
    y = np.asarray(y, float)
    cf, beta, r, alpha = _solve_parts(params, P, y, space, time, mean)
    k = covariance(params, Q, P, space, time)  # (m, n)
    mu = beta + k @ alpha
    Kik = linalg.cho_solve(cf, k.T)  # (n, m)
    var = params[0] - np.einsum("ij,ji->i", k, Kik)
    if mean != "zero":
        one = np.ones(len(y))
        Ki1 = linalg.cho_solve(cf, one)
        var = var + (1 - one @ Kik) ** 2 / (one @ Ki1)  # the cost of estimating the mean
    var = np.maximum(var, 0.0)
    return mu, var, var + params[3]


def variogram(P, y, dist_edges, lags):
    """Rows (distance band low, high, lag, pairs, semivariance). Lags are exact differences in t."""
    P, y = np.asarray(P, float), np.asarray(y, float)
    i, j = np.triu_indices(len(y), 1)
    h = np.hypot(P[i, 0] - P[j, 0], P[i, 1] - P[j, 1])
    u = np.abs(P[i, 2] - P[j, 2])
    g = 0.5 * (y[i] - y[j]) ** 2
    out = []
    for lag in lags:
        for lo, hi in zip(dist_edges[:-1], dist_edges[1:]):
            m = (u == lag) & (h >= lo) & (h < hi)
            out.append((lo, hi, lag, int(m.sum()), float(g[m].mean()) if m.any() else float("nan")))
    return out


def model_variogram(model, h, u):
    sill, rs, rt, nugget = model["params"]
    c = sill * FAMILIES[model["space"]](np.asarray(h) / rs) * FAMILIES[model["time"]](np.asarray(u) / rt)
    return sill + nugget - c


def detrend_and_krige(loc, t, y, coords, train, test, detrend="time", space="exponential", time="exponential"):
    """Remove a mean structure fitted on the training rows (st_model: "time" = mu + b(t), "additive" =
    mu + a(s) + b(t), or "none"), krige the residuals, and add the two back at the test rows. Returns the
    prediction, the variance of a new observation, the fitted kriging model and the mean part at the test rows.

    Only the kriging part's uncertainty is in the variance. Under "additive", a(s) at a location not in training
    is filled by st_model's inverse-distance mean, and that error is in no variance: the interval is too narrow
    at new locations. Under "time", the locations' levels stay in the residual and the spatial covariance
    carries them (with a long range in time)."""
    from st_model import fit as fit_mean, predict as predict_mean

    loc, t, y = np.asarray(loc), np.asarray(t, float), np.asarray(y, float)
    P = np.column_stack([[coords[k][0] for k in loc], [coords[k][1] for k in loc], t])
    if detrend == "none":
        base_tr, base_te = np.zeros(train.sum()), np.zeros(test.sum())
    else:
        mp = fit_mean(detrend, loc[train], t[train], y[train], coords)
        base_tr = predict_mean(mp, loc[train], t[train], coords)
        base_te = predict_mean(mp, loc[test], t[test], coords)
    m = fit(P[train], y[train] - base_tr, space, time)
    mu, _, var_obs = predict(m, P[train], y[train] - base_tr, P[test])
    return base_te + mu, var_obs, m, base_te


def main():
    from st_model import evaluate

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("table", "location", "time", "x", "y", "value"):
        p.add_argument(name)
    p.add_argument("--cutoff", type=float, required=True)
    p.add_argument("--detrend", choices=["time", "additive", "none"], default="time",
                   help="the mean structure removed before kriging (see detrend_and_krige)")
    p.add_argument("--space", dest="space_family", choices=list(FAMILIES), default="exponential")
    p.add_argument("--time", dest="time_family", choices=list(FAMILIES), default="exponential")
    p.add_argument("--blocks", action="store_true")
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.location}", "{a.time}", "{a.x}", "{a.y}", "{a.value}" from \'{a.table}\'').fetchall()
    kept = [r for r in rows if None not in r]
    print(f"rows {len(rows)}, with a missing field {len(rows) - len(kept)} (left out), used {len(kept)}")
    loc = np.array([r[0] for r in kept])
    t = np.array([r[1] for r in kept], float)
    y = np.array([r[4] for r in kept], float)
    coords = {}
    for r in kept:
        coords.setdefault(r[0], (float(r[2]), float(r[3])))
    print(f"locations {len(coords)}, times {len(np.unique(t))}")

    masks = evaluate(["additive"], loc, t, y, coords, a.cutoff, a.seed, a.blocks, return_masks=True)["masks"]
    z = stats.norm.ppf(1 - a.alpha / 2)
    for kind in ("future_known", "new_location", "future_new"):
        err_m, err_k, cover = [], [], []
        for train, test in masks[kind]:
            if not test.any() or not train.any():
                continue
            pred, var_obs, m, base_te = detrend_and_krige(loc, t, y, coords, train, test, a.detrend,
                                                          a.space_family, a.time_family)
            err_m.append(y[test] - base_te)
            err_k.append(y[test] - pred)
            cover.append(np.abs(y[test] - pred) <= z * np.sqrt(var_obs))
            sill, rs, rt, nug = m["params"]
            print(f"  {kind}: fold of {int(test.sum())} test rows; sill {sill:.4g}, range in space {rs:.4g}, "
                  f"range in time {rt:.4g}, nugget {nug:.4g}" + ("  (a parameter at its edge)" if m["at_edge"] else ""))
        em, ek, cv = np.concatenate(err_m), np.concatenate(err_k), np.concatenate(cover)
        print(f"{kind}: RMSE {a.detrend} {np.sqrt(np.mean(em ** 2)):.4g}, with kriging {np.sqrt(np.mean(ek ** 2)):.4g}; "
              f"{1 - a.alpha:g} interval coverage {cv.mean():.3f}")


if __name__ == "__main__":
    main()

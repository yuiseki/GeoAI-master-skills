"""The effect of a binary treatment under no unmeasured confounding given the adjustment set: regression
adjustment, inverse probability weighting and augmented IPW (doubly robust), with the diagnostics that say
whether the data can carry them. None of these makes an effect causal; the adjustment set and the
assumptions come from the design, not from this script.

    fit_logit    propensity p = P(treated | x) by logistic regression (Newton). Stops when Newton does not
                 converge, which is what complete separation by x does (no row has a comparison). Fitted p
                 below 1e-8 or above 1 - 1e-8 without separation are counted (extreme): rows almost without
                 comparison, a matter for the overlap diagnostics.
    effects      naive difference of means, and
                 ra    regression adjustment: a linear outcome model per arm, the difference of the predictions
                       averaged over all rows (ATE) or the treated (ATT). Right if the outcome model is right.
                 ipw   normalised (Hajek) weights 1/p and 1/(1-p) (ATE), or p/(1-p) on the untreated (ATT).
                       Right if the propensity model is right.
                 aipw  the outcome model plus the weighted residuals. Right if either model is right; wrong if
                       both are. se_if is its influence-function standard error (rows independent).
                 x_ps sets the covariates of the propensity model when they differ from the outcome model's.
    diagnostics  propensity by arm, the share outside [lo, 1-lo], and per arm the effective sample size of the
                 weights (sum w)^2 / sum w^2 and the largest weight's share
    balance      standardised mean difference of each covariate before and after weighting
    trim         rows with lo <= p <= 1-lo. The estimate is then for a different population: say so.
    bootstrap    refits both models on resampled rows, or whole clusters (cluster=): units that share
                 treatment or shocks (a region, a city) are not independent rows. Draws that fail (separation,
                 an arm too small for its model) are counted.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python estimate_effect.py TABLE OUTCOME TREATMENT X1 [X2 ...] \\
        [--ps-covariates Z1 ...] [--target ate|att] [--trim 0.05] [--cluster COLUMN] [--boot 500]
"""

import argparse

import numpy as np

METHODS = ("ra", "ipw", "aipw")


def _design(x):
    x = np.asarray(x, float)
    x = x.reshape(len(x), -1)
    return np.c_[np.ones(len(x)), x]


def fit_logit(x, t, maxiter=100, tol=1e-10, eps=1e-8):
    Z, t = _design(x), np.asarray(t, float)
    b = np.zeros(Z.shape[1])
    for it in range(maxiter):
        p = 1 / (1 + np.exp(-np.clip(Z @ b, -35, 35)))
        H = (Z * (p * (1 - p))[:, None]).T @ Z
        try:
            step = np.linalg.solve(H, Z.T @ (t - p))
        except np.linalg.LinAlgError:
            raise ValueError("propensity model is singular or the treatment is separated by the covariates")
        b += step
        if np.max(np.abs(step)) < tol:
            break
    else:
        raise ValueError("propensity model did not converge: the treatment may be separated by the covariates")
    p = 1 / (1 + np.exp(-np.clip(Z @ b, -35, 35)))
    return {"p": p, "coef": b, "iterations": it + 1, "extreme": int(np.sum((p < eps) | (p > 1 - eps)))}


def _arm_predictions(y, t, x):
    X = _design(x)
    out = []
    for arm in (0, 1):
        m = t == arm
        if m.sum() <= X.shape[1] or np.linalg.matrix_rank(X[m]) < X.shape[1]:
            raise ValueError(f"arm {arm} has too few rows or too little variation for its outcome model")
        beta = np.linalg.lstsq(X[m], y[m], rcond=None)[0]
        out.append(X @ beta)
    return out


def effects(y, t, x, x_ps=None, target="ate", p=None):
    if target not in ("ate", "att"):
        raise ValueError("target is ate or att")
    y, t = np.asarray(y, float), np.asarray(t).astype(int)
    if p is None:
        p = fit_logit(x if x_ps is None else x_ps, t)["p"]
    mu0, mu1 = _arm_predictions(y, t, x)
    naive = y[t == 1].mean() - y[t == 0].mean()
    if target == "ate":
        ra = np.mean(mu1 - mu0)
        w1, w0 = t / p, (1 - t) / (1 - p)
        ipw = np.sum(w1 * y) / np.sum(w1) - np.sum(w0 * y) / np.sum(w0)
        psi = mu1 - mu0 + t * (y - mu1) / p - (1 - t) * (y - mu0) / (1 - p)
    else:
        treated = t == 1
        ra = np.mean(y[treated] - mu0[treated])
        w0 = (1 - t) * p / (1 - p)
        ipw = y[treated].mean() - np.sum(w0 * y) / np.sum(w0)
        psi = (t * (y - mu0) - w0 * (y - mu0)) / t.mean()
    aipw = psi.mean()
    return {"naive": float(naive), "ra": float(ra), "ipw": float(ipw), "aipw": float(aipw),
            "se_if": float(np.std(psi - aipw, ddof=1) / np.sqrt(len(y))), "n": len(y), "treated": int(t.sum())}


def _weights(t, p, target):
    return t / p + (1 - t) / (1 - p) if target == "ate" else t + (1 - t) * p / (1 - p)


def diagnostics(t, p, lo=0.05, target="ate"):
    t, p = np.asarray(t).astype(int), np.asarray(p, float)
    w = _weights(t, p, target)
    out = {"outside": float(np.mean((p < lo) | (p > 1 - lo))), "lo": lo, "n": [], "ess": [], "max_share": [],
           "p_quantiles": []}
    for arm in (0, 1):
        m = t == arm
        out["n"].append(int(m.sum()))
        out["ess"].append(float(w[m].sum() ** 2 / np.sum(w[m] ** 2)))
        out["max_share"].append(float(w[m].max() / w[m].sum()))
        out["p_quantiles"].append([float(q) for q in np.quantile(p[m], [0, 0.05, 0.5, 0.95, 1])])
    return out


def balance(x, t, p, names, target="ate"):
    x = np.asarray(x, float).reshape(len(t), -1)
    t = np.asarray(t).astype(int)
    w = _weights(t, np.asarray(p, float), target)
    out = []
    for j, name in enumerate(names):
        a, b = x[t == 1, j], x[t == 0, j]
        sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        before = (a.mean() - b.mean()) / sd if sd > 0 else 0.0
        wa, wb = w[t == 1], w[t == 0]
        after = (np.sum(wa * a) / wa.sum() - np.sum(wb * b) / wb.sum()) / sd if sd > 0 else 0.0
        out.append({"covariate": name, "smd_before": float(before), "smd_after": float(after)})
    return out


def trim(p, lo):
    p = np.asarray(p, float)
    return (p >= lo) & (p <= 1 - lo)


def bootstrap(y, t, x, x_ps=None, target="ate", n_boot=500, seed=0, cluster=None):
    y, t = np.asarray(y, float), np.asarray(t).astype(int)
    x = np.asarray(x, float).reshape(len(y), -1)
    x_ps = x if x_ps is None else np.asarray(x_ps, float).reshape(len(y), -1)
    r = np.random.default_rng(seed)
    if cluster is not None:
        _, codes = np.unique(np.asarray(cluster), return_inverse=True)
        members = [np.flatnonzero(codes == c) for c in range(codes.max() + 1)]
    draws, failed = {m: [] for m in METHODS}, 0
    for _ in range(n_boot):
        if cluster is None:
            idx = r.integers(0, len(y), len(y))
        else:
            idx = np.concatenate([members[c] for c in r.integers(0, len(members), len(members))])
        try:
            if t[idx].min() == t[idx].max():
                raise ValueError("one arm only")
            e = effects(y[idx], t[idx], x[idx], x_ps[idx], target)
        except ValueError:
            failed += 1
            continue
        for m in METHODS:
            draws[m].append(e[m])
    out = {"failed": failed, "used": n_boot - failed, "clusters": None if cluster is None else len(members)}
    for m in METHODS:
        d = np.array(draws[m])
        out[m] = {"se": float(d.std(ddof=1)) if len(d) > 1 else float("nan"),
                  "ci": [float(q) for q in np.quantile(d, [0.025, 0.975])] if len(d) else [float("nan")] * 2}
    return out


def main():
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table")
    ap.add_argument("outcome")
    ap.add_argument("treatment", help="0 / 1")
    ap.add_argument("covariates", nargs="+", help="the adjustment set from the design")
    ap.add_argument("--ps-covariates", nargs="+", help="propensity covariates, if not the same")
    ap.add_argument("--target", choices=["ate", "att"], default="ate")
    ap.add_argument("--trim", type=float, default=0.0, help="drop rows with p outside [lo, 1-lo] and refit")
    ap.add_argument("--lo", type=float, default=0.05, help="bound for the overlap diagnostic")
    ap.add_argument("--cluster", help="resample whole clusters in the bootstrap")
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    ps_cols = a.ps_covariates or a.covariates
    cols = list(dict.fromkeys([a.outcome, a.treatment, *a.covariates, *ps_cols] + ([a.cluster] if a.cluster else [])))
    df = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").df()
    n0 = len(df)
    df = df.dropna()
    if len(df) != n0:
        raise SystemExit(f"{n0 - len(df)} of {n0} rows have a missing value; decide how to handle them first")
    t = df[a.treatment].to_numpy()
    if not set(np.unique(t)) <= {0, 1}:
        raise SystemExit("the treatment must be 0 or 1")
    t = t.astype(int)
    y = df[a.outcome].to_numpy(float)
    x, z = df[a.covariates].to_numpy(float), df[ps_cols].to_numpy(float)
    g = df[a.cluster].to_numpy() if a.cluster else None
    f = fit_logit(z, t)
    p = f["p"]
    print(f"rows {len(y)}, treated {t.sum()}, untreated {len(t) - t.sum()}, target {a.target}")
    if f["extreme"]:
        print(f"propensity below 1e-8 or above 1 - 1e-8: {f['extreme']} rows (almost no comparison)")
    if a.trim > 0:
        keep = trim(p, a.trim)
        print(f"trim {a.trim}: kept {keep.sum()} of {len(y)} (treated {t[keep].sum()} of {t.sum()}); the estimate "
              "is now for the rows with overlap, a different population")
        y, t, x, z = y[keep], t[keep], x[keep], z[keep]
        g = g[keep] if g is not None else None
        p = fit_logit(z, t)["p"]
    d = diagnostics(t, p, a.lo, a.target)
    print(f"propensity outside [{a.lo}, {1 - a.lo}]: {d['outside']:.3f} of rows")
    for arm in (0, 1):
        q = d["p_quantiles"][arm]
        print(f"  arm {arm}: n {d['n'][arm]}, p min {q[0]:.3g} median {q[2]:.3g} max {q[4]:.3g}, "
              f"effective n of weights {d['ess'][arm]:.0f}, largest weight's share {d['max_share'][arm]:.3f}")
    print("balance (standardised mean difference, before -> after weighting):")
    for b in balance(z, t, p, ps_cols, a.target):
        print(f"  {b['covariate']}: {b['smd_before']:+.3f} -> {b['smd_after']:+.3f}")
    e = effects(y, t, x, z, a.target, p=p)
    bs = bootstrap(y, t, x, z, a.target, a.boot, a.seed, g)
    unit = f"clusters ({bs['clusters']})" if g is not None else "rows"
    print(f"naive difference of means {e['naive']:.4g}")
    for m in METHODS:
        print(f"  {m}: {e[m]:.4g}  bootstrap se {bs[m]['se']:.3g} (resampling {unit}), "
              f"95% interval {bs[m]['ci'][0]:.4g} to {bs[m]['ci'][1]:.4g}")
    print(f"  aipw influence-function se (rows independent) {e['se_if']:.3g}")
    if bs["failed"]:
        print(f"WARNING: {bs['failed']} of {a.boot} bootstrap draws failed (separation or a tiny arm)")
    spread = max(e[m] for m in METHODS) - min(e[m] for m in METHODS)
    if spread > 2 * bs["aipw"]["se"]:
        print(f"WARNING: the estimators disagree by {spread:.3g}, more than 2 bootstrap se: at least one of the "
              "outcome and propensity models is wrong, or the overlap is poor")


if __name__ == "__main__":
    main()

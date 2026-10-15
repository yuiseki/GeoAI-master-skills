"""Multilevel (hierarchical, mixed) linear models: rows nested in groups, with a random intercept per group,
optionally a random slope, a second level, and the group means of the regressors (Mundlak).

    icc_anova  between-group variance tau2, within-group variance sigma2 and ICC = tau2 / (tau2 + sigma2)
               from the one-way ANOVA table (n0 replaces n for unequal group sizes). A negative tau2 is
               reported as 0 with at_zero=True: the data show no more spread between groups than chance.
    shrink     partial pooling of group means: overall mean + weight x (group mean - overall mean), weight =
               tau2 / (tau2 + sigma2 / n). Small groups and noisy rows are pulled hardest towards the overall
               mean; the overall mean is the precision-weighted one (1 / (tau2 + sigma2 / n)).
    fit        REML (or ML) through statsmodels MixedLM. Returns the fixed coefficients and their standard
               errors, se_ols (the same regressors treated as independent rows, for comparison), tau2,
               sigma2, the ICC, the random intercept of each group (its partial pooling), slope_var for
               random slopes, nested_var for a lower level inside each group, share of the variance by level,
               and the optimiser's warnings (a variance at the boundary 0 or no convergence is reported, not
               hidden).
               mundlak=True adds the group mean of each regressor; the regressor's coefficient is then the
               within-group slope (the same as unit fixed effects), and the group mean's coefficient is the
               between minus within difference. The random intercept alone assumes the group effect is
               unrelated to the regressors; when it is not, its slope mixes in the between-group difference.
The likelihood is maximised by BFGS with a tight gradient tolerance; statsmodels' default (L-BFGS) stopped
short of the maximum on a flat REML surface (WDI life expectancy, 211 countries: tau2 1.6e-4 below the value an
independent REML found). If BFGS does not converge, the default is used and optimiser says so.
ML divides the between sum of squares by the number of groups, not that minus one: with few groups it
underestimates tau2. Prefer REML for variances; compare fixed effects across models fitted with ML.

Usage:
    uvx --from 'duckdb>=1.5.5' --with statsmodels python multilevel_fit.py TABLE TARGET F1 [F2 ...] \\
        --group COLUMN [--nested COLUMN] [--random-slope F1] [--mundlak] [--ml]
"""

import argparse
import warnings

import numpy as np


def _codes(group):
    labels, codes = np.unique(np.asarray(group), return_inverse=True)
    return labels, codes, np.bincount(codes)


def group_means(X, group):
    X = np.asarray(X, float)
    _, codes, n = _codes(group)
    sums = np.zeros((len(n), X.shape[1]))
    np.add.at(sums, codes, X)
    return (sums / n[:, None])[codes]


def icc_anova(y, group):
    y = np.asarray(y, float)
    labels, codes, n = _codes(group)
    G, N = len(n), len(y)
    means = np.bincount(codes, y) / n
    msw = np.sum((y - means[codes]) ** 2) / (N - G)
    msb = np.sum(n * (means - y.mean()) ** 2) / (G - 1)
    n0 = (N - np.sum(n ** 2) / N) / (G - 1)
    tau2 = (msb - msw) / n0
    at_zero = tau2 < 0
    tau2 = max(tau2, 0.0)
    return {"tau2": tau2, "sigma2": msw, "icc": tau2 / (tau2 + msw), "n0": n0, "groups": G,
            "at_zero": bool(at_zero)}


def shrink(y, group, tau2, sigma2, mu=None):
    y = np.asarray(y, float)
    labels, codes, n = _codes(group)
    raw = np.bincount(codes, y) / n
    if mu is None:
        w = 1 / (tau2 + sigma2 / n)
        mu = np.sum(w * raw) / np.sum(w)
    weight = tau2 / (tau2 + sigma2 / n)
    return {"group": labels, "n": n, "raw": raw, "pooled": mu + weight * (raw - mu), "weight": weight,
            "mu": mu}


def fit(y, X, group, names=None, random_slope=None, mundlak=False, nested=None, reml=True):
    import statsmodels.api as sm
    from statsmodels.regression.mixed_linear_model import VCSpec

    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    names = list(names) if names is not None else [f"x{j}" for j in range(X.shape[1])]
    group = np.asarray(group)
    if mundlak:
        X = np.c_[X, group_means(X, group)]
        names = names + [f"{n}_group_mean" for n in names]
    D = np.c_[np.ones(len(y)), X]
    cols = ["const"] + names
    re_cols = ["const"] + list(random_slope or [])
    exog_re = D[:, [cols.index(c) for c in re_cols]]
    exog_vc = None
    if nested is not None:
        nested = np.asarray(nested)
        names_vc, mats = [], []
        for g in np.unique(group):  # MixedLM orders the groups as sorted labels
            sub = np.unique(nested[group == g])  # codes are read within the group: ward 1 of two cities differ
            names_vc.append([str(c) for c in sub])
            mats.append((nested[group == g][:, None] == sub[None, :]).astype(float))
        exog_vc = VCSpec(["nested"], [names_vc], [mats])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = sm.MixedLM(y, D, groups=group, exog_re=exog_re, exog_vc=exog_vc)
        m = model.fit(reml=reml, method="bfgs", gtol=1e-10, maxiter=2000)
        optimiser = "bfgs"
        if not m.converged:  # fall back to statsmodels' default; converged and warnings still report it
            m = model.fit(reml=reml)
            optimiser = "default"
    ols = sm.OLS(y, D).fit()
    k = D.shape[1]
    cov_re = np.atleast_2d(np.asarray(m.cov_re))
    tau2 = float(cov_re[0, 0])
    sigma2 = float(m.scale)
    nested_var = float(m.vcomp[0]) if nested is not None else 0.0
    total = tau2 + nested_var + sigma2
    out = {
        "coef": dict(zip(cols, np.asarray(m.fe_params)[:k])),
        "se": dict(zip(cols, np.asarray(m.bse_fe)[:k])),
        "se_ols": dict(zip(cols, np.asarray(ols.bse))),
        "coef_ols": dict(zip(cols, np.asarray(ols.params))),
        "tau2": tau2, "sigma2": sigma2, "icc": tau2 / (tau2 + sigma2),
        "slope_var": {c: float(cov_re[i, i]) for i, c in enumerate(re_cols) if i > 0},
        "random_effects": {g: float(np.asarray(v)[0]) for g, v in m.random_effects.items()},
        "groups": len(np.unique(group)), "converged": bool(m.converged), "optimiser": optimiser,
        "warnings": sorted({str(w.message).splitlines()[0] for w in caught}),
    }
    if nested is not None:
        out["nested_var"] = nested_var
        out["share"] = {"group": tau2 / total, "nested": nested_var / total, "residual": sigma2 / total}
    return out


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("target")
    p.add_argument("features", nargs="*")
    p.add_argument("--group", required=True, help="the upper level (prefecture, region, municipality)")
    p.add_argument("--nested", help="a lower level inside each group (municipality inside prefecture)")
    p.add_argument("--random-slope", nargs="+", default=[], help="features whose slope varies by group")
    p.add_argument("--mundlak", action="store_true", help="add group means: the slope becomes within-group")
    p.add_argument("--ml", action="store_true", help="maximum likelihood instead of REML")
    a = p.parse_args()
    cols = [a.target, *a.features, a.group] + ([a.nested] if a.nested else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; drop them first")
    nf = len(a.features)
    y = np.array([r[0] for r in kept], float)
    X = np.array([r[1:1 + nf] for r in kept], float).reshape(len(y), nf)
    group = np.array([r[1 + nf] for r in kept])
    nested = np.array([r[2 + nf] for r in kept]) if a.nested else None
    _, _, n = _codes(group)
    print(f"rows {len(y)}, groups {len(n)} ({a.group}), rows per group min {n.min()} median "
          f"{int(np.median(n))} max {n.max()}, groups with fewer than 5 rows {int(np.sum(n < 5))}")
    i = icc_anova(y, group)
    print(f"target alone, ANOVA by {a.group}: tau2 {i['tau2']:.4g}, sigma2 {i['sigma2']:.4g}, ICC {i['icc']:.3f}"
          + (" (tau2 below 0, set to 0)" if i["at_zero"] else ""))
    r = fit(y, X, group, a.features, a.random_slope, a.mundlak, nested, reml=not a.ml)
    method = "ML" if a.ml else "REML"
    if nested is None:
        print(f"after the features, {method}: tau2 {r['tau2']:.4g}, sigma2 {r['sigma2']:.4g}, ICC {r['icc']:.3f}")
    else:
        print(f"after the features, {method}: {a.group} {r['tau2']:.4g}, {a.nested} within {a.group} "
              f"{r['nested_var']:.4g}, rows {r['sigma2']:.4g}; share "
              + ", ".join(f"{k} {v:.3f}" for k, v in r["share"].items()))
    for c in r["coef"]:
        print(f"  {c}: coef {r['coef'][c]:.4g} se {r['se'][c]:.3g}   "
              f"(rows as independent: coef {r['coef_ols'][c]:.4g} se {r['se_ols'][c]:.3g})")
    for c, v in r["slope_var"].items():
        print(f"  slope variance of {c} across groups {v:.4g}")
    if not r["converged"] or r["warnings"]:
        print("WARNING: " + "; ".join(r["warnings"] or ["did not converge"]))


if __name__ == "__main__":
    main()

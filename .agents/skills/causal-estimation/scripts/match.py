"""The effect on the treated (ATT) by nearest-neighbour matching with replacement, with the Abadie-Imbens
standard error. As with the other estimators, matching does not make an effect causal: it relies on the same
no-unmeasured-confounding assumption given the matching covariates.

Each treated row gets its k nearest controls (all tied controls are kept, so a set can be larger than k):
    on covariates   distance sum_d (x_d - x'_d)^2 / var(x_d) (diagonal inverse variance), or the full
                    Mahalanobis distance (--metric mahalanobis)
    on the propensity (--on ps)  absolute difference of the logit of p from a logistic regression
--caliper drops treated rows whose nearest control is farther than it (in the distance's own units: standard
deviations for the diagonal metric, logit units for ps). The estimate is then for the treated that were kept:
say so.

--bias-adjust (Abadie and Imbens 2011): the control outcome is moved to the treated row's covariates,
y_control + mu0(x_treated) - mu0(x_control), with mu0 a linear regression of y on x fitted on the matched
controls (each as often as it is used); that is, mu0(x_treated) - mu0(x_control) is subtracted from each
matched difference.

Standard error (Abadie and Imbens 2006, ATT, matching with replacement): the variance of the matched
differences around the ATT over the treated, plus for every control the square of the share of a match it
gives minus its sum of squared shares, times its conditional variance; the conditional variance of a row is
estimated from its nearest row in the same arm, (y_i - y_l)^2 / 2. The bootstrap is not valid for matching
with replacement and is not offered.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python match.py TABLE OUTCOME TREATMENT X1 [X2 ...] [--k 1] \\
        [--on covariates|ps] [--metric diagonal|mahalanobis] [--caliper C] [--bias-adjust]
"""

import argparse

import numpy as np

from estimate_effect import fit_logit


def _scale(x, metric):
    x = np.asarray(x, float)
    if metric == "diagonal":
        v = x.var(0)
        if (v == 0).any():
            raise SystemExit("a matching covariate does not vary")
        return 1 / v
    return np.linalg.inv(np.cov(x, rowvar=False).reshape(x.shape[1], x.shape[1]))


def _dist(a, B, W):
    d = B - a
    return (d * d * W).sum(1) if W.ndim == 1 else np.einsum("ij,jk,ik->i", d, W, d)


def nearest_controls(xt, xc, W, k, caliper=None):
    """For each treated row, the indices of its k nearest controls, ties at the k-th distance included;
    an empty array when even the nearest is beyond the caliper (in distance units, not squared)."""
    out = []
    for a in np.asarray(xt, float):
        d = _dist(a, np.asarray(xc, float), W)
        kth = np.partition(d, min(k, len(d)) - 1)[min(k, len(d)) - 1]
        idx = np.flatnonzero(d <= kth + 1e-12 * max(1.0, kth))
        if caliper is not None and np.sqrt(d.min()) > caliper:
            idx = np.array([], int)
        out.append(idx)
    return out


def smd(xt, xc):
    xt, xc = np.asarray(xt, float), np.asarray(xc, float)
    s = np.sqrt((xt.var(0, ddof=1) + xc.var(0, ddof=1)) / 2)
    return (xt.mean(0) - xc.mean(0)) / np.where(s > 0, s, np.nan)


def att_matching(y, t, x, k=1, on="covariates", metric="diagonal", caliper=None, bias_adjust=False):
    y, t, x = np.asarray(y, float), np.asarray(t, int), np.asarray(x, float).reshape(len(y), -1)
    if t.sum() == 0 or (t == 0).sum() == 0:
        raise SystemExit("matching needs treated and control rows")
    if on == "ps":
        p = fit_logit(x, t)["p"]
        z = np.log(p / (1 - p))[:, None]
        W, label = np.ones(1), "logit propensity"
    else:
        z, W = x, _scale(x, metric)
        label = "covariates, " + metric
    T, C = np.flatnonzero(t == 1), np.flatnonzero(t == 0)
    sets = nearest_controls(z[T], z[C], W, k, caliper)
    kept = np.array([len(s) > 0 for s in sets])
    if not kept.any():
        raise SystemExit("no treated row has a control within the caliper")
    Tk = T[kept]
    sets = [s for s in sets if len(s)]
    diffs = np.array([y[i] - y[C[s]].mean() for i, s in zip(Tk, sets)])
    if bias_adjust:
        flat = np.concatenate([C[s] for s in sets])
        X1 = np.c_[np.ones(len(flat)), x[flat]]
        beta = np.linalg.lstsq(X1, y[flat], rcond=None)[0][1:]
        diffs = diffs - np.array([(x[i] - x[C[s]].mean(0)) @ beta for i, s in zip(Tk, sets)])
    att = float(diffs.mean())

    # Abadie-Imbens (2006) variance for the ATT with replacement.
    n1 = len(Tk)
    share, share2 = np.zeros(len(C)), np.zeros(len(C))
    for s in sets:
        share[s] += 1 / len(s)
        share2[s] += 1 / len(s) ** 2
    sigma2 = np.zeros(len(y))
    for arm in (T, C):
        if len(arm) < 2:
            continue
        Wa = _scale(x, metric) if on == "covariates" else W
        for i in arm:
            others = arm[arm != i]
            d = _dist(z[i], z[others], Wa)
            near = others[np.flatnonzero(d <= d.min() + 1e-12 * max(1.0, d.min()))]
            sigma2[i] = ((y[i] - y[near].mean()) ** 2) * len(near) / (len(near) + 1)
    var = (((diffs - att) ** 2).sum() + ((share ** 2 - share2) * sigma2[C]).sum()) / n1 ** 2
    used = np.unique(np.concatenate(sets))
    return {"att": att, "se": float(np.sqrt(var)), "matched_treated": int(n1), "dropped_treated": int((~kept).sum()),
            "controls_used": int(len(used)), "max_reuse": float(share.max()), "metric": label,
            "smd_before": smd(x[T], x[C]),
            "smd_after": smd(x[Tk], np.vstack([x[C[s]].mean(0) for s in sets]))}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("outcome")
    p.add_argument("treatment")
    p.add_argument("covariates", nargs="+")
    p.add_argument("--k", type=int, default=1)
    p.add_argument("--on", choices=["covariates", "ps"], default="covariates")
    p.add_argument("--metric", choices=["diagonal", "mahalanobis"], default="diagonal")
    p.add_argument("--caliper", type=float)
    p.add_argument("--bias-adjust", action="store_true")
    a = p.parse_args()

    import duckdb

    cols = [a.outcome, a.treatment, *a.covariates]
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; decide how to treat them first")
    y = np.array([r[0] for r in kept], float)
    t = np.array([r[1] for r in kept], int)
    x = np.array([r[2:] for r in kept], float)
    r = att_matching(y, t, x, a.k, a.on, a.metric, a.caliper, a.bias_adjust)
    print(f"rows {len(kept)}: treated {int(t.sum())}, controls {int((t == 0).sum())}; matched on {r['metric']}, "
          f"k {a.k}{', caliper ' + str(a.caliper) if a.caliper else ''}{', bias-adjusted' if a.bias_adjust else ''}")
    print(f"treated matched {r['matched_treated']}, dropped by the caliper {r['dropped_treated']}; controls used "
          f"{r['controls_used']}, the most used one carries {r['max_reuse']:.1f} matches")
    print(f"ATT {r['att']:.6g} (Abadie-Imbens se {r['se']:.4g})")
    print("standardised mean differences, before -> after matching:")
    for nme, b, aft in zip(a.covariates, r["smd_before"], r["smd_after"]):
        print(f"  {nme:<16} {b:+.3f} -> {aft:+.3f}")


if __name__ == "__main__":
    main()

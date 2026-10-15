"""Checks on the data for a causal design: support (overlap) by stratum, the effect by standardisation over
strata that have both treated and untreated rows, exposure from neighbours' treatment, and how strong a
hidden confounder would have to be to explain an estimate. These check what data can check; the
assumptions that make an estimate causal (no unmeasured confounding, consistency, no interference beyond
the exposure written down) are not testable from the same data.

    diff_in_means   mean outcome of treated minus untreated: an association, a causal effect only if the
                    groups are exchangeable
    overlap         per stratum, the treated and untreated counts; a stratum lacking one has no support
    standardize     per-stratum difference of means, averaged with the stratum shares of all rows (ATE) or of
                    the treated (ATT). A stratum without support gives effect None and is listed: the data
                    say nothing about it. supported_only=True averages over the supported strata only, which
                    is a different population: say so.
    ols             least squares with an intercept: coefficients (intercept first) and R2. A model gives a
                    number where there is no support by carrying the shape it learnt elsewhere.
    neighbour_share share of a unit's neighbours that are treated (an exposure mapping for spillover)
    distance_to_treated  distance to the nearest other treated unit (projected coordinates)
    bias_grid       estimate - gamma x delta for a hidden binary confounder that adds gamma to the outcome
                    and differs by delta in prevalence between treated and untreated (after the adjustment
                    made). Linear and additive by assumption; it shows what strength would explain the
                    estimate away, not whether such a confounder exists.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python design_checks.py TABLE OUTCOME TREATMENT STRATUM \\
        [--target ate|att]
"""

import argparse

import numpy as np


def diff_in_means(y, t):
    y, t = np.asarray(y, float), np.asarray(t)
    return float(y[t == 1].mean() - y[t == 0].mean())


def overlap(t, strata):
    t, strata = np.asarray(t), np.asarray(strata)
    out = []
    for s in np.unique(strata):
        m = strata == s
        nt, nu = int(np.sum(t[m] == 1)), int(np.sum(t[m] == 0))
        out.append({"stratum": s.item() if hasattr(s, "item") else s, "treated": nt, "untreated": nu,
                    "supported": nt > 0 and nu > 0})
    return out


def standardize(y, t, strata, target="ate", supported_only=False):
    if target not in ("ate", "att"):
        raise ValueError("target is ate or att")
    y, t, strata = np.asarray(y, float), np.asarray(t), np.asarray(strata)
    pop = t == 1 if target == "att" else np.ones(len(t), bool)
    effects, weights, unsupported = [], [], []
    for row in overlap(t, strata):
        m = strata == row["stratum"]
        w = np.sum(pop & m)
        if w == 0:
            continue
        if not row["supported"]:
            unsupported.append(row["stratum"])
            continue
        effects.append(y[m & (t == 1)].mean() - y[m & (t == 0)].mean())
        weights.append(w)
    lost = sum(np.sum(pop & (strata == s)) for s in unsupported) / np.sum(pop)
    effect = float(np.average(effects, weights=weights)) if effects else None
    if unsupported and not supported_only:
        effect = None
    return {"effect": effect, "target": target, "unsupported": unsupported, "unsupported_share": float(lost)}


def ols(y, X):
    y = np.asarray(y, float)
    D = np.c_[np.ones(len(y)), np.asarray(X, float).reshape(len(y), -1)]
    b = np.linalg.lstsq(D, y, rcond=None)[0]
    resid = y - D @ b
    tss = np.sum((y - y.mean()) ** 2)
    return b, float(1 - resid @ resid / tss) if tss > 0 else float("nan")


def neighbour_share(t, neighbours):
    t = np.asarray(t)
    return np.array([t[list(nb)].mean() if len(nb) else 0.0 for nb in neighbours])


def distance_to_treated(t, xy):
    t, xy = np.asarray(t), np.asarray(xy, float)
    treated = np.flatnonzero(t == 1)
    out = np.full(len(t), np.inf)
    for i in range(len(t)):
        others = treated[treated != i]
        if len(others):
            out[i] = np.sqrt(((xy[others] - xy[i]) ** 2).sum(axis=1)).min()
    return out


def bias_grid(estimate, gammas, deltas):
    adj = [[estimate - g * d for d in deltas] for g in gammas]
    sign = np.sign(estimate)
    return {"gammas": list(gammas), "deltas": list(deltas), "adjusted": adj,
            "explains": [[bool(np.sign(v) != sign or abs(v) < 1e-12) for v in row] for row in adj]}


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("outcome")
    p.add_argument("treatment", help="a 0/1 column")
    p.add_argument("stratum", help="the column of adjustment strata (a region, a combination of levels)")
    p.add_argument("--target", default="ate", choices=["ate", "att"])
    a = p.parse_args()
    rows = duckdb.sql(f'select "{a.outcome}", "{a.treatment}", "{a.stratum}" from \'{a.table}\'').fetchall()
    kept = [r for r in rows if None not in r]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; drop them first")
    y = np.array([r[0] for r in kept], float)
    t = np.array([r[1] for r in kept])
    if set(np.unique(t).tolist()) - {0, 1}:
        raise SystemExit("the treatment must be 0/1")
    s = np.array([r[2] for r in kept])
    print(f"rows {len(y)}, treated {int(t.sum())}, difference in means {diff_in_means(y, t):.4g} (association)")
    table = overlap(t, s)
    bad = [r for r in table if not r["supported"]]
    print(f"strata {len(table)}, without both treated and untreated rows {len(bad)}")
    for r in bad:
        print(f"  {r['stratum']}: treated {r['treated']}, untreated {r['untreated']}")
    r = standardize(y, t, s, a.target)
    if r["effect"] is None:
        part = standardize(y, t, s, a.target, supported_only=True)
        print(f"{a.target.upper()} is not supported by the data: {r['unsupported_share']:.1%} of the target rows "
              f"are in strata without support. Over the supported strata only: {part['effect']}")
    else:
        print(f"{a.target.upper()} by standardisation over {a.stratum}: {r['effect']:.4g}")


if __name__ == "__main__":
    main()

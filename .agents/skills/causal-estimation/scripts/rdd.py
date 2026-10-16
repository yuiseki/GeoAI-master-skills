"""Regression discontinuity: the jump of the outcome at a cutoff of a running variable, by local linear fits on
each side with triangular weights (1 - |x - c| / h inside the bandwidth h).

The assumption is continuity: without the treatment, the outcome's mean would pass the cutoff smoothly. It
fails when units can place themselves on the chosen side (manipulation; the density check counts the units
just below and just above), or when something else also changes at the cutoff (covariate jumps show some of
it). The estimate is the effect for units at the cutoff, not elsewhere.

    sharp      treatment switches at the cutoff: tau = right intercept - left intercept. Standard error: HC1
               sandwiches of the two weighted fits, added
    fuzzy      the cutoff only raises the chance of treatment: tau = outcome jump / treatment jump, with a
               delta-method standard error from the same rows. Like IV, it estimates the effect for the units
               whose treatment the cutoff changes
    density_check  units in [c - h, c) against [c, c + h), two-sided binomial test of an even split (a crude
               check: it assumes a flat density near c)

There is no automatic bandwidth: give one or more (--bandwidth) and read how the estimate moves; a narrow
bandwidth has less bias from curvature and more variance. Bias-corrected robust intervals are not computed.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python rdd.py TABLE OUTCOME RUNNING --cutoff C \\
        --bandwidth H [H2 ...] [--treatment D] [--covariates X1 ...] [--placebo-cutoffs C1 ...] [--density-h H0]
"""

import argparse

import numpy as np
from scipy import stats


def _side(x, c, h, side):
    u = np.asarray(x, float) - c
    m = (u >= 0) & (u < h) if side == 1 else (u < 0) & (-u < h)
    return m, u


def local_linear_jump(y, x, c, h, side, extra=None):
    """Weighted least squares of y on (1, x - c) on one side; intercept, its HC1 variance, rows, and the
    pieces needed to combine fits (bread, design, weights, residuals)."""
    m, u = _side(x, c, h, side)
    if m.sum() < 3:
        raise SystemExit(f"{int(m.sum())} rows on the {'right' if side else 'left'} side within the bandwidth {h}; "
                         "widen it")
    X = np.c_[np.ones(m.sum()), u[m]]
    w = 1 - np.abs(u[m]) / h
    yy = np.asarray(y, float)[m]
    bread = np.linalg.inv(X.T @ (X * w[:, None]))
    beta = bread @ X.T @ (w * yy)
    e = yy - X @ beta
    n = len(yy)
    meat = X.T @ (X * ((w * e) ** 2)[:, None])
    V = bread @ meat @ bread * n / (n - 2)
    return {"intercept": float(beta[0]), "var": float(V[0, 0]), "n": int(n), "bread": bread, "X": X, "w": w, "e": e}


def sharp(y, x, c, h):
    r, l = local_linear_jump(y, x, c, h, 1), local_linear_jump(y, x, c, h, 0)
    return {"tau": r["intercept"] - l["intercept"], "se": float(np.sqrt(r["var"] + l["var"])), "n_left": l["n"],
            "n_right": r["n"], "h": h}


def fuzzy(y, d, x, c, h):
    sides = {s: (local_linear_jump(y, x, c, h, s), local_linear_jump(d, x, c, h, s)) for s in (0, 1)}
    jy = sides[1][0]["intercept"] - sides[0][0]["intercept"]
    jd = sides[1][1]["intercept"] - sides[0][1]["intercept"]
    if abs(jd) < 1e-12:
        raise SystemExit("the treatment does not jump at the cutoff")
    tau = jy / jd
    var = 0.0
    for s in (0, 1):
        fy, fd = sides[s]
        u = (fy["e"] - tau * fd["e"]) / jd  # the linearised error of tau from this side
        meat = fy["X"].T @ (fy["X"] * ((fy["w"] * u) ** 2)[:, None])
        n = fy["n"]
        var += (fy["bread"] @ meat @ fy["bread"])[0, 0] * n / (n - 2)
    return {"tau": float(tau), "se": float(np.sqrt(var)), "first_stage": float(jd), "outcome_jump": float(jy),
            "n_left": sides[0][0]["n"], "n_right": sides[1][0]["n"], "h": h}


def density_check(x, c, h):
    u = np.asarray(x, float) - c
    left, right = int(((u < 0) & (u >= -h)).sum()), int(((u >= 0) & (u < h)).sum())
    p = stats.binomtest(right, left + right, 0.5).pvalue if left + right else float("nan")
    return {"left": left, "right": right, "p": float(p)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("outcome")
    p.add_argument("running")
    p.add_argument("--cutoff", type=float, required=True)
    p.add_argument("--bandwidth", type=float, nargs="+", required=True)
    p.add_argument("--treatment")
    p.add_argument("--covariates", nargs="*", default=[])
    p.add_argument("--placebo-cutoffs", type=float, nargs="*", default=[])
    p.add_argument("--density-h", type=float)
    a = p.parse_args()

    import duckdb

    cols = [a.outcome, a.running] + ([a.treatment] if a.treatment else []) + a.covariates
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    k = 3 if a.treatment else 2
    main_rows = [r for r in rows if all(v is not None for v in r[:k])]
    print(f"rows {len(rows)}, with the outcome, running variable{' and treatment' if a.treatment else ''} "
          f"{len(main_rows)}; cutoff {a.cutoff:g}")
    col = lambda rs, i: np.array([r[i] for r in rs], float)
    y, x = col(main_rows, 0), col(main_rows, 1)
    d = col(main_rows, 2) if a.treatment else None
    for h in a.bandwidth:
        r = fuzzy(y, d, x, a.cutoff, h) if a.treatment else sharp(y, x, a.cutoff, h)
        extra = f", treatment jump {r['first_stage']:.4g}" if a.treatment else ""
        print(f"h {h:g}: tau {r['tau']:.6g} (se {r['se']:.4g}), rows left {r['n_left']} right {r['n_right']}{extra}")
    h0 = a.bandwidth[0]
    for i, name in enumerate(a.covariates):
        cr = [r for r in main_rows if r[k + i] is not None]
        r = sharp(col(cr, k + i), col(cr, 1), a.cutoff, h0)
        print(f"covariate {name} at the cutoff (h {h0:g}, {len(cr)} rows): jump {r['tau']:+.4g} (se {r['se']:.3g}); "
              "a jump means something else changes at the cutoff")
    for pc in a.placebo_cutoffs:
        same = x >= a.cutoff if pc >= a.cutoff else x < a.cutoff  # stay on one side of the real cutoff
        r = sharp(y[same], x[same], pc, h0)
        print(f"placebo cutoff {pc:g} (h {h0:g}): tau {r['tau']:+.4g} (se {r['se']:.3g})")
    dc = density_check(x, a.cutoff, a.density_h or h0 / 4)
    print(f"density check (h {a.density_h or h0 / 4:g}): {dc['left']} just below, {dc['right']} just above, "
          f"binomial p {dc['p']:.3g}")


if __name__ == "__main__":
    main()

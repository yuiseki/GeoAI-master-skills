"""Diagnostics of an ordinary least-squares fit whose coefficients will be read or tested: the spread of
the residuals (Breusch-Pagan, Koenker's studentised form: n R^2 of the squared residuals on the design; and White's
test, which adds the squares and cross products),
the shape of the residuals (Jarque-Bera), and the conditioning of the design (condition number of the
raw design, which depends on the units of the columns, and of the design with each column scaled to
unit length, which does not). Plain and HC3 (heteroskedasticity-robust) standard errors side by side.

These matter when coefficients are interpreted or tested. A model compared by out-of-fold scores does
not need them. A rejection is not a verdict: Breusch-Pagan rejecting means plain standard errors are
not to be trusted (use HC3, or model the variance); Jarque-Bera rejecting at large n says little
about the validity of the intervals; a large scaled condition number says some coefficients are not
pinned down separately.

Usage:
    uvx --with numpy --with scipy --with duckdb python regression_diagnostics.py TABLE TARGET FEATURE [...]
"""

import argparse

import numpy as np
from scipy import stats


def ols(X, y):
    X, y = np.asarray(X, float), np.asarray(y, float)
    n, k = X.shape
    if np.linalg.matrix_rank(X) < k:
        raise SystemExit(f"the design has rank {np.linalg.matrix_rank(X)} < {k} columns; drop or combine "
                         "columns that are linear combinations of others")
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    sigma2 = e @ e / (n - k)
    h = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    meat = X.T @ (X * (e / (1 - h))[:, None] ** 2)
    return {"beta": beta, "resid": e, "se": np.sqrt(np.diag(xtx_inv) * sigma2),
            "se_hc3": np.sqrt(np.diag(xtx_inv @ meat @ xtx_inv)), "n": n, "k": k}


def breusch_pagan(resid, X):
    """Koenker's studentised Breusch-Pagan: n R^2 of resid^2 on X (with its constant), chi^2 with k - 1 df."""
    X = np.asarray(X, float)
    u = np.asarray(resid, float) ** 2
    fit = np.linalg.lstsq(X, u, rcond=None)[0]
    r2 = 1 - ((u - X @ fit) ** 2).sum() / ((u - u.mean()) ** 2).sum()
    lm = len(u) * r2
    return float(lm), float(stats.chi2.sf(lm, X.shape[1] - 1))


def white(resid, X):
    """White's test: Breusch-Pagan on the design plus the squares and cross products of its non-constant
    columns, so that a spread changing with |x| or with x1 x2 is seen too."""
    X = np.asarray(X, float)
    vary = [j for j in range(X.shape[1]) if np.ptp(X[:, j]) > 0]
    extra = [X[:, i] * X[:, j] for a, i in enumerate(vary) for j in vary[a:]]
    Z = np.c_[X, np.column_stack(extra)] if extra else X
    keep = np.linalg.matrix_rank(Z)
    if keep < Z.shape[1]:  # binary columns square to themselves; drop dependent columns
        q, r = np.linalg.qr(Z)
        Z = Z[:, np.abs(np.diag(r)) > 1e-10 * np.abs(np.diag(r)).max()]
    return breusch_pagan(resid, Z)


def jarque_bera(resid):
    z = np.asarray(resid, float)
    z = z - z.mean()
    m2 = (z ** 2).mean()
    s = (z ** 3).mean() / m2 ** 1.5
    k = (z ** 4).mean() / m2 ** 2
    jb = len(z) / 6 * (s ** 2 + (k - 3) ** 2 / 4)
    return float(jb), float(stats.chi2.sf(jb, 2)), float(s), float(k)


def condition_numbers(X):
    X = np.asarray(X, float)
    scaled = X / np.linalg.norm(X, axis=0)
    return {"raw": float(np.linalg.cond(X)), "scaled": float(np.linalg.cond(scaled))}


def diagnose(X, y, names):
    r = ols(X, y)
    return {**r, "names": names, "bp": breusch_pagan(r["resid"], X), "white": white(r["resid"], X),
            "jb": jarque_bera(r["resid"]),
            "cond": condition_numbers(X)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    a = p.parse_args()

    import duckdb

    cols = [a.target, *a.features]
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    print(f"rows {len(rows)}, with no missing value {len(kept)}")
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; decide how to treat them first")
    y = np.array([r[0] for r in kept], float)
    X = np.c_[np.ones(len(kept)), np.array([r[1:] for r in kept], float)]
    d = diagnose(X, y, ["const", *a.features])
    print(f"{'term':<20}{'coef':>12}{'se':>12}{'se HC3':>12}")
    for nme, b, s, h in zip(d["names"], d["beta"], d["se"], d["se_hc3"]):
        print(f"{nme:<20}{b:>12.5g}{s:>12.5g}{h:>12.5g}")
    lm, pb = d["bp"]
    lw, pw = d["white"]
    jb, pj, sk, ku = d["jb"]
    print(f"Breusch-Pagan (studentised) LM {lm:.4g}, p {pb:.4g}: "
          + ("the residual spread changes with the features; read the HC3 column" if pb <= 0.05 else
             "no evidence that the spread changes with the features (it may change with something else)"))
    print(f"White (squares and cross products added) LM {lw:.4g}, p {pw:.4g}: Breusch-Pagan sees only a spread "
          "that changes linearly with the features")
    print(f"Jarque-Bera {jb:.4g}, p {pj:.4g} (skewness {sk:.3g}, kurtosis {ku:.3g}); with {d['n']} rows, "
          "a rejection alone does not invalidate the intervals")
    c = d["cond"]
    print(f"condition number: raw {c['raw']:.4g} (depends on the units of the columns), "
          f"columns scaled to unit length {c['scaled']:.4g}")


if __name__ == "__main__":
    main()

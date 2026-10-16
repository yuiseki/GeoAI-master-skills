"""Instrumental variables: two-stage least squares (2SLS) with exogenous controls, the first stage that says
whether the instruments are strong enough, and the Anderson-Rubin confidence set that stays valid when they
are not.

The instrument must move the treatment (relevance: the first stage shows it), must not reach the outcome
except through the treatment (exclusion), and must be as good as random given the controls (independence).
Exclusion and independence cannot be tested from the data with one instrument. With effects that differ
between people and a monotone instrument, 2SLS estimates the effect on the compliers (LATE), the people whose
treatment the instrument changes, not the average effect.

    tsls            coefficients of the endogenous columns then the controls; standard errors homoskedastic,
                    heteroskedasticity-robust (HC1, the default 'se') and, with cluster=, CR1 by cluster;
                    the first-stage F of the excluded instruments (classical) and their partial R^2 for one
                    endogenous column
    anderson_rubin  one endogenous column, one instrument: the set of effects b for which, after removing the
                    controls, y - b x is unrelated to z (F test, homoskedastic). It is an interval when the
                    instrument is strong, and may be two rays or the whole line when it is weak; it does not
                    rely on the instrument being strong.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python iv.py TABLE OUTCOME ENDOGENOUS \\
        --instruments Z1 [Z2 ...] [--controls W1 ...] [--cluster COLUMN]
"""

import argparse

import numpy as np
from scipy import stats


def _cols(a, n):
    a = np.asarray(a, float)
    return a.reshape(n, -1)


def tsls(y, x, z, w, cluster=None):
    y = np.asarray(y, float)
    n = len(y)
    x, z, w = _cols(x, n), _cols(z, n), _cols(w, n)
    X, Z = np.c_[x, w], np.c_[z, w]
    if np.linalg.matrix_rank(Z) < Z.shape[1] or z.shape[1] < x.shape[1]:
        raise SystemExit("the instruments with the controls are collinear, or fewer than the endogenous columns")
    Xh = Z @ np.linalg.lstsq(Z, X, rcond=None)[0]
    bread = np.linalg.inv(Xh.T @ Xh)
    beta = bread @ Xh.T @ y
    e = y - X @ beta
    k = X.shape[1]
    se_h = np.sqrt(np.diag(bread) * (e @ e) / (n - k))
    meat = Xh.T @ (Xh * (e ** 2)[:, None])
    se = np.sqrt(np.diag(bread @ meat @ bread) * n / (n - k))
    out = {"beta": beta, "se": se, "se_homoskedastic": se_h, "n": n}
    if cluster is not None:
        c = np.unique(np.asarray(cluster), return_inverse=True)[1]
        G = c.max() + 1
        S = np.zeros((G, k))
        np.add.at(S, c, Xh * e[:, None])
        V = bread @ (S.T @ S) @ bread * G / (G - 1) * (n - 1) / (n - k)
        out["se_cluster"] = np.sqrt(np.diag(V))
        out["clusters"] = int(G)
    if x.shape[1] == 1:
        rss_u = ((x[:, 0] - Z @ np.linalg.lstsq(Z, x[:, 0], rcond=None)[0]) ** 2).sum()
        rss_r = ((x[:, 0] - w @ np.linalg.lstsq(w, x[:, 0], rcond=None)[0]) ** 2).sum()
        l = z.shape[1]
        out["first_stage_F"] = float(((rss_r - rss_u) / l) / (rss_u / (n - Z.shape[1])))
        out["partial_r2"] = float(1 - rss_u / rss_r)
    return out


class ARSet:
    """{b : a b^2 + c1 b + c0 <= 0}: an interval, two rays, the whole line, or empty."""

    def __init__(self, a, c1, c0):
        self.a, self.c1, self.c0 = a, c1, c0
        disc = c1 * c1 - 4 * a * c0
        self.lo = self.hi = None
        if abs(a) < 1e-14 * max(1.0, abs(c1), abs(c0)):
            self.kind = "ray"
        elif a > 0:
            self.kind = "interval" if disc >= 0 else "empty"
        else:
            self.kind = "two rays" if disc > 0 else "whole line"
        if disc >= 0 and abs(a) > 0:
            r = sorted([(-c1 - np.sqrt(disc)) / (2 * a), (-c1 + np.sqrt(disc)) / (2 * a)])
            self.lo, self.hi = float(r[0]), float(r[1])

    def contains(self, b):
        return bool(self.a * b * b + self.c1 * b + self.c0 <= 0)

    def __str__(self):
        if self.kind == "interval":
            return f"[{self.lo:.6g}, {self.hi:.6g}]"
        if self.kind == "two rays":
            return f"(-inf, {self.lo:.6g}] U [{self.hi:.6g}, inf)"
        return self.kind


def anderson_rubin(y, x, z, w, alpha=0.05):
    y = np.asarray(y, float)
    n = len(y)
    x, z, w = _cols(x, n), _cols(z, n), _cols(w, n)
    if x.shape[1] != 1 or z.shape[1] != 1:
        raise SystemExit("this Anderson-Rubin set is for one endogenous column and one instrument")
    M = lambda v: v - w @ np.linalg.lstsq(w, v, rcond=None)[0]
    yt, xt, zt = M(y), M(x[:, 0]), M(z[:, 0])
    df = n - w.shape[1] - 1
    q = stats.f.ppf(1 - alpha, 1, df) / df
    zz, a1, a2 = zt @ zt, zt @ yt, zt @ xt
    yy, xy, xx = yt @ yt, xt @ yt, xt @ xt
    # (1 + q) (z'u_b)^2 / z'z - q u_b'u_b <= 0 with u_b = y - b x.
    a = (1 + q) * a2 * a2 / zz - q * xx
    c1 = -2 * (1 + q) * a1 * a2 / zz + 2 * q * xy
    c0 = (1 + q) * a1 * a1 / zz - q * yy
    return ARSet(a, c1, c0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("outcome")
    p.add_argument("endogenous")
    p.add_argument("--instruments", nargs="+", required=True)
    p.add_argument("--controls", nargs="*", default=[])
    p.add_argument("--cluster")
    a = p.parse_args()

    import duckdb

    cols = [a.outcome, a.endogenous, *a.instruments, *a.controls] + ([a.cluster] if a.cluster else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    print(f"rows {len(rows)}, with no missing value {len(kept)}")
    if len(kept) != len(rows):
        raise SystemExit("decide how to treat the rows with missing values first")
    arr = lambda i, j=None: np.array([r[i] if j is None else r[i:j] for r in kept], float)
    y, x = arr(0), arr(1)
    li = len(a.instruments)
    z = arr(2, 2 + li)
    w = np.c_[np.ones(len(kept)), arr(2 + li, 2 + li + len(a.controls))] if a.controls else np.ones((len(kept), 1))
    cl = np.array([r[-1] for r in kept]) if a.cluster else None
    r = tsls(y, x, z, w, cl)
    ols = np.linalg.lstsq(np.c_[x, w], y, rcond=None)[0][0]
    print(f"first stage: F of the excluded instruments {r['first_stage_F']:.4g}, partial R^2 {r['partial_r2']:.4g}")
    extra = f", clustered {r['se_cluster'][0]:.4g} ({r['clusters']} clusters)" if cl is not None else ""
    print(f"2SLS effect of {a.endogenous}: {r['beta'][0]:.6g} (se robust {r['se'][0]:.4g}, homoskedastic "
          f"{r['se_homoskedastic'][0]:.4g}{extra}); OLS {ols:.6g}")
    if li == 1:
        print(f"Anderson-Rubin 95% set (homoskedastic, valid with a weak instrument): {anderson_rubin(y, x, z, w)}")
    print("exclusion and independence of the instruments are assumptions; this output cannot check them")


if __name__ == "__main__":
    main()

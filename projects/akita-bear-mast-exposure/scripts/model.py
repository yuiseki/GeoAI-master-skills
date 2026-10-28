"""The recalibration: logit P(report in cell c, year t) = alpha_t + logit(B_env_c) + beta * mast_scarcity(t) * E(c).

logit(B_env) is an offset (coefficient 1), so the saved B_env is not refitted. alpha_t absorbs the level of each
training year (a mast term alone would be the same within a year and is not identifiable from alpha_t). There
is no exposure main effect. The cells of a target year are ranked by logit(B_env) + beta * s(target) * E.
"""

import numpy as np

EPS = 1e-6


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p) - np.log1p(-p)


def fit(years, tol=1e-10, max_iter=100):
    """years: [(offset, x, y)] per training year, x = s(t) * E. Newton steps on (alpha_1..alpha_T, beta)."""
    T = len(years)
    theta = np.zeros(T + 1)
    for it in range(max_iter):
        g = np.zeros(T + 1)
        H = np.zeros((T + 1, T + 1))
        for t, (off, x, y) in enumerate(years):
            eta = off + theta[t] + theta[T] * x
            p = 1 / (1 + np.exp(-eta))
            w = p * (1 - p)
            r = np.asarray(y, dtype=float) - p
            g[t] = r.sum()
            g[T] += (x * r).sum()
            H[t, t] = w.sum()
            H[t, T] = H[T, t] = (w * x).sum()
            H[T, T] += (w * x * x).sum()
        step = np.linalg.solve(H, g)
        theta += step
        if np.abs(step).max() < tol:
            break
    se = float(np.sqrt(np.linalg.inv(H)[T, T]))
    return {"alpha": theta[:T].tolist(), "beta": float(theta[T]), "se_beta": se, "iterations": it + 1}


def score(benv, e, beta, s):
    return logit(benv) + beta * s * np.asarray(e, dtype=float)

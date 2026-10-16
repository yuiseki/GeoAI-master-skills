"""Points that inhibit each other: the Strauss process, simulated and fitted by maximum pseudo-likelihood.

    density            proportional to beta^n gamma^s(x), s(x) the number of pairs closer than r. gamma = 1 is a
                       Poisson process with intensity beta; gamma < 1 makes close pairs rare (regular patterns:
                       shops spacing themselves, trees competing); gamma = 0 forbids them (a hard core). gamma
                       > 1 has no valid density on the plane: the Strauss model cannot describe clustering.
    conditional_intensity  lambda(u | x) = beta gamma^t(u, x), t the number of points of x within r of u: the
                       chance of a point at u given the rest of the pattern
    simulate           birth-death Metropolis-Hastings (Geyer and Moller 1994) in a rectangle, started empty
    fit                maximum pseudo-likelihood: maximise sum log lambda(x_i | x without x_i) - integral of
                       lambda(u | x) over the window, by the Berman-Turner quadrature (data and grid dummy
                       points, a weighted Poisson regression of 1 / weight on t). Border correction: only
                       points and dummies at least r inside the window count, since their neighbourhoods are
                       fully observed.
    profile_r          the pseudo-likelihood's maximum over candidate interaction distances r
    gnz_residual       n - integral of lambda(u | x) over the (eroded) window: by the Georgii-Nguyen-Zessin
                       formula its expectation is 0 under the model, for any fitted or true parameters that
                       generated the pattern

The pseudo-likelihood is not the likelihood: its standard errors from the curvature are too small when the
interaction is strong; this script does not give them. Units are projected (metres); the window is a
rectangle; beta is constant (no covariates).

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python gibbs.py POINTS X Y --window XMIN XMAX YMIN YMAX \\
        --r R1 R2 ... [--grid 60] [--simulate 39]
"""

import argparse

import numpy as np


def _area(window):
    x0, x1, y0, y1 = window
    return (x1 - x0) * (y1 - y0)


def pair_count(x, y, r):
    d2 = (x[:, None] - x[None]) ** 2 + (y[:, None] - y[None]) ** 2
    return int(((d2 < r * r).sum() - len(x)) // 2)


def neighbours_within(ux, uy, x, y, r):
    """For each u, the number of points of (x, y) closer than r (a point at u itself counts)."""
    ux, uy = np.atleast_1d(ux), np.atleast_1d(uy)
    if len(x) == 0:
        return np.zeros(len(ux), int)
    d2 = (ux[:, None] - x[None]) ** 2 + (uy[:, None] - y[None]) ** 2
    return (d2 < r * r).sum(1)


def conditional_intensity(ux, uy, x, y, beta, gamma, r):
    return beta * gamma ** neighbours_within(ux, uy, x, y, r)


def simulate(beta, gamma, r, window, steps=None, seed=0):
    x0, x1, y0, y1 = window
    A = _area(window)
    rng = np.random.default_rng(seed)
    steps = steps or int(200 * beta * A) + 2000
    px, py = [], []
    for _ in range(steps):
        n = len(px)
        if rng.random() < 0.5:  # birth
            ux, uy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            t = neighbours_within(ux, uy, np.array(px), np.array(py), r)[0] if n else 0
            if rng.random() < beta * gamma ** t * A / (n + 1):
                px.append(ux)
                py.append(uy)
        elif n:  # death
            i = rng.integers(n)
            ax, ay = np.array(px[:i] + px[i + 1:]), np.array(py[:i] + py[i + 1:])
            t = neighbours_within(px[i], py[i], ax, ay, r)[0] if n > 1 else 0
            lam = beta * gamma ** t
            if lam == 0 or rng.random() < n / (A * lam):
                px.pop(i)
                py.pop(i)
    return np.array(px), np.array(py)


def _quadrature(x, y, window, r, grid):
    """Data and dummy points with Berman-Turner weights (cell area / points in the cell), kept only at least r
    inside the window (border correction). Returns ux, uy, weight, is_data, t (neighbours other than itself)."""
    x0, x1, y0, y1 = window
    gx = x0 + (np.arange(grid) + 0.5) * (x1 - x0) / grid
    gy = y0 + (np.arange(grid) + 0.5) * (y1 - y0) / grid
    GX, GY = np.meshgrid(gx, gy)
    ux = np.r_[x, GX.ravel()]
    uy = np.r_[y, GY.ravel()]
    is_data = np.r_[np.ones(len(x), bool), np.zeros(grid * grid, bool)]
    cx = np.minimum(((ux - x0) / (x1 - x0) * grid).astype(int), grid - 1)
    cy = np.minimum(((uy - y0) / (y1 - y0) * grid).astype(int), grid - 1)
    cell = cy * grid + cx
    per_cell = np.bincount(cell, minlength=grid * grid)
    w = (_area(window) / grid ** 2) / per_cell[cell]
    t = neighbours_within(ux, uy, x, y, r) - is_data  # a data point does not count itself
    inside = (ux >= x0 + r) & (ux <= x1 - r) & (uy >= y0 + r) & (uy <= y1 - r)
    return ux[inside], uy[inside], w[inside], is_data[inside], t[inside]


def log_pseudolikelihood(theta, t, w, is_data):
    """theta = (log beta, log gamma)."""
    eta = theta[0] + theta[1] * t
    return float(eta[is_data].sum() - (w * np.exp(eta)).sum())


def fit(x, y, window, r, grid=60):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ux, uy, w, is_data, t = _quadrature(x, y, window, r, grid)
    if not is_data.any():
        raise SystemExit("no point lies at least r inside the window")
    X = np.c_[np.ones(len(t)), t]
    theta = np.array([np.log(is_data.sum() / w.sum()), 0.0])
    hard_core = not (t[is_data] > 0).any()
    if hard_core:  # no data point has a neighbour: gamma's estimate is 0 (log gamma -> -infinity)
        free = t == 0
        theta = np.array([np.log(is_data.sum() / w[free].sum()), -np.inf])
        ll = float(is_data.sum() * theta[0] - (w[free] * np.exp(theta[0])).sum())
    else:
        for _ in range(100):
            mu = w * np.exp(X @ theta)
            grad = X[is_data].sum(0) - X.T @ mu
            H = X.T @ (X * mu[:, None])
            step = np.linalg.solve(H, grad)
            theta = theta + step
            if np.abs(step).max() < 1e-10:
                break
        ll = log_pseudolikelihood(theta, t, w, is_data)
    return {"beta": float(np.exp(theta[0])), "gamma": float(np.exp(theta[1])), "r": r, "log_pl": ll,
            "points_used": int(is_data.sum()), "dummies": int((~is_data).sum()), "hard_core": hard_core}


def profile_r(x, y, window, rs, grid=60):
    """Each r's fit. The border correction drops points near the edge, more for larger r, so the pseudo-
    likelihoods are compared on the points and dummies kept by the largest r."""
    rmax = max(rs)
    out = []
    for r in rs:
        f = fit(x, y, window, r, grid)
        ux, uy, w, is_data, t = _quadrature(np.asarray(x, float), np.asarray(y, float), window, r, grid)
        x0, x1, y0, y1 = window
        keep = (ux >= x0 + rmax) & (ux <= x1 - rmax) & (uy >= y0 + rmax) & (uy <= y1 - rmax)
        theta = np.array([np.log(f["beta"]), np.log(f["gamma"]) if f["gamma"] > 0 else -np.inf])
        with np.errstate(invalid="ignore"):
            eta = theta[0] + np.where(t[keep] > 0, theta[1] * t[keep], 0.0)
        f["log_pl_common"] = float(eta[is_data[keep]].sum() - (w[keep] * np.exp(eta)).sum())
        out.append(f)
    return out


def gnz_residual(x, y, window, beta, gamma, r, grid=200):
    """n - integral of lambda(u | x), both over the window eroded by r (a fine grid for the integral)."""
    x0, x1, y0, y1 = window
    e = (x0 + r, x1 - r, y0 + r, y1 - r)
    gx = e[0] + (np.arange(grid) + 0.5) * (e[1] - e[0]) / grid
    gy = e[2] + (np.arange(grid) + 0.5) * (e[3] - e[2]) / grid
    GX, GY = np.meshgrid(gx, gy)
    lam = conditional_intensity(GX.ravel(), GY.ravel(), x, y, beta, gamma, r)
    n_in = int(((x >= e[0]) & (x <= e[1]) & (y >= e[2]) & (y <= e[3])).sum())
    return n_in - float(lam.mean() * _area(e))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("points")
    p.add_argument("x")
    p.add_argument("y")
    p.add_argument("--where", default="true")
    p.add_argument("--window", type=float, nargs=4, required=True, metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    p.add_argument("--r", type=float, nargs="+", required=True, help="candidate interaction distances")
    p.add_argument("--grid", type=int, default=60)
    p.add_argument("--simulate", type=int, default=0,
                   help="simulate this many patterns from the chosen fit and compare the pair count")
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.x}", "{a.y}" from \'{a.points}\' where {a.where}').fetchall()
    x, y = np.array([r[0] for r in rows], float), np.array([r[1] for r in rows], float)
    x0, x1, y0, y1 = a.window
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    print(f"points {len(x)}, inside the window {int(inside.sum())} (the others are left out)")
    x, y = x[inside], y[inside]
    fits = profile_r(x, y, a.window, a.r, a.grid)
    for f in fits:
        print(f"  r {f['r']:g}: beta {f['beta']:.4g}, gamma {f['gamma']:.3f}, points used {f['points_used']}, "
              f"log pseudo-likelihood (common border) {f['log_pl_common']:.2f}")
    best = max(fits, key=lambda f: f["log_pl_common"])
    print(f"chosen r {best['r']:g}: gamma {best['gamma']:.3f}" + ("  (r is at the edge of the candidates)"
                                                                  if best["r"] in (min(a.r), max(a.r)) else ""))
    if best["gamma"] > 1:
        print("gamma > 1: close pairs are more common than under Poisson. The Strauss model has no valid density "
              "then; the pattern is clustered or its intensity varies. Use a cluster or Cox model, or model the "
              "trend first")
        return
    print(f"GNZ residual (points minus the integrated conditional intensity, eroded window): "
          f"{gnz_residual(x, y, a.window, best['beta'], best['gamma'], best['r']):+.2f}")
    if a.simulate:
        s_obs = pair_count(x, y, best["r"])
        sims = [pair_count(*simulate(best["beta"], best["gamma"], best["r"], a.window, seed=k), best["r"])
                for k in range(a.simulate)]
        rank = (np.array(sims) <= s_obs).mean()
        print(f"pairs closer than r: observed {s_obs}, simulated from the fit median {np.median(sims):.0f} "
              f"(share of simulations at or below the observed {rank:.2f})")


if __name__ == "__main__":
    main()

"""Poisson point processes as models of how a point pattern was generated: fit a log-linear intensity by the
point-process likelihood, compare it with Poisson regression on grid counts, simulate from a fitted or
assumed process, and check a fit with statistics the fit did not use.

    intensity        lambda(s): expected points per unit area at s. The expected count in a region is the
                     integral of lambda over it; the counts in disjoint regions are independent Poisson.
    log-linear       log lambda(s) = b0 + b1 x1(s) + ...; homogeneous when only b0.
    likelihood       sum_i log lambda(s_i) - integral of lambda over the window. The integral is computed
                     on a quadrature (cell centres and areas, quadrature()); fit_poisson_process maximises it
                     by Newton's method and gives standard errors from the curvature.
    conditional_fit  the same pattern conditioned on its count n: the locations are n independent draws
                     with density lambda / integral. The slopes are the same as the full fit's; the intercept
                     (the overall level) is not estimated.
    fit_grid_poisson Poisson regression of cell counts with offset log(area). Its score has the same form
                     as the likelihood's, with each point's covariate replaced by its cell's and the
                     integral by one value per cell: a fine grid approximates the likelihood; a coarse grid
                     or one whose origin moves changes the answer when the covariate varies inside cells.
                     area is the cell's area inside the window, not the full cell.
    simulate_poisson inhomogeneous Poisson by thinning (lam_max >= lambda everywhere)
    simulate_thomas  parents Poisson(kappa per unit area), each with Poisson(mu) offspring at Gaussian(sigma)
                     displacements: clustering made by the process itself (contagion, attraction)
    cell_means       the covariate averaged over each cell, for grid Poisson; the centre value of a coarse
                     cell misses the covariate's variation inside it
    bump_field       a smooth random field (a sum of Gaussian bumps scaled to sd 1): an observed covariate,
                     or an unobserved environment that makes a Cox-like pattern when it enters log lambda
    pearson_dispersion  sum (count - expected)^2 / expected / (cells - parameters): 1 for a Poisson fit that
                     explains the counts; above 1 when something is left
    mean_nn_distance, monte_carlo_p  a statistic of the pattern against patterns simulated from the fit

Points and windows are in projected units (metres); the window here is a rectangle. Points observed are not
points that occurred: if detection varies in space, the fitted intensity is occurrence x detection.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python point_process.py POINTS_TABLE X Y \\
        --window XMIN XMAX YMIN YMAX [--covariate-x] [--cell SIZE]
"""

import argparse
import math

import numpy as np


def quadrature(window, n):
    x0, x1, y0, y1 = window
    xs = x0 + (np.arange(n) + 0.5) * (x1 - x0) / n
    ys = y0 + (np.arange(n) + 0.5) * (y1 - y0) / n
    X, Y = np.meshgrid(xs, ys)
    return np.c_[X.ravel(), Y.ravel()], np.full(n * n, (x1 - x0) * (y1 - y0) / (n * n))


def expected_count(intensity, window, n=200):
    q, w = quadrature(window, n)
    return float(np.sum(w * intensity(q)))


def _newton(obs_x, Xq, wq, iters=100):
    """Maximise sum(obs) . b - sum_j wq_j exp(Xq_j b); obs_x is the sum of the observed design rows."""
    b = np.zeros(Xq.shape[1])
    total = obs_x[0]  # the intercept column sums to the count
    b[0] = math.log(total / wq.sum())
    for _ in range(iters):
        mu = wq * np.exp(Xq @ b)
        grad = obs_x - Xq.T @ mu
        H = (Xq * mu[:, None]).T @ Xq
        step = np.linalg.solve(H, grad)
        b += step
        if np.max(np.abs(step)) < 1e-12:
            break
    mu = wq * np.exp(Xq @ b)
    H = (Xq * mu[:, None]).T @ Xq
    return b, np.sqrt(np.diag(np.linalg.inv(H)))


def fit_poisson_process(X_points, X_quad, w_quad):
    Xp = np.c_[np.ones(len(X_points)), np.asarray(X_points, float).reshape(len(X_points), -1)]
    Xq = np.c_[np.ones(len(X_quad)), np.asarray(X_quad, float).reshape(len(X_quad), -1)]
    w = np.asarray(w_quad, float)
    b, se = _newton(Xp.sum(axis=0), Xq, w)
    loglik = float(np.sum(Xp @ b) - np.sum(w * np.exp(Xq @ b)))
    return {"beta": b, "se": se, "loglik": loglik, "n": len(Xp)}


def conditional_fit(X_points, X_quad, w_quad, iters=100):
    Xp = np.asarray(X_points, float).reshape(len(X_points), -1)
    Xq = np.asarray(X_quad, float).reshape(len(X_quad), -1)
    w = np.asarray(w_quad, float)
    n = len(Xp)
    b = np.zeros(Xp.shape[1])
    for _ in range(iters):
        p = w * np.exp(Xq @ b)
        p /= p.sum()
        mean = Xq.T @ p
        grad = Xp.sum(axis=0) - n * mean
        H = n * ((Xq * p[:, None]).T @ Xq - np.outer(mean, mean))
        step = np.linalg.solve(H, grad)
        b += step
        if np.max(np.abs(step)) < 1e-12:
            break
    return {"beta": b}


def fit_grid_poisson(counts, X_cells, area):
    c = np.asarray(counts, float)
    X = np.c_[np.ones(len(c)), np.asarray(X_cells, float).reshape(len(c), -1)]
    a = np.asarray(area, float)
    b, se = _newton(X.T @ c, X, a)
    return {"beta": b, "se": se, "zeros": float(np.mean(c == 0))}


def grid_counts(points, window, cell, origin=0.0):
    x0, x1, y0, y1 = window
    pts = np.asarray(points, float)
    ex = np.arange(x0 - (cell - origin) % cell if origin else x0, x1 + cell, cell)
    ey = np.arange(y0 - (cell - origin) % cell if origin else y0, y1 + cell, cell)
    ex, ey = ex[ex < x1 + 1e-12], ey[ey < y1 + 1e-12]
    centres, area, counts = [], [], []
    for xa in ex:
        for ya in ey:
            xb, yb = xa + cell, ya + cell
            w = min(xb, x1) - max(xa, x0)
            h = min(yb, y1) - max(ya, y0)
            if w <= 1e-12 or h <= 1e-12:
                continue
            inside = (pts[:, 0] >= xa) & (pts[:, 0] < xb) & (pts[:, 1] >= ya) & (pts[:, 1] < yb)
            centres.append(((max(xa, x0) + min(xb, x1)) / 2, (max(ya, y0) + min(yb, y1)) / 2))
            area.append(w * h)
            counts.append(int(inside.sum()))
    return {"centres": np.array(centres), "area": np.array(area), "counts": np.array(counts)}


def intensity_upper(intensity, window, n=300, margin=1.2):
    """A bound for thinning: the largest intensity on a fine grid and along the window's edges, with a margin."""
    x0, x1, y0, y1 = window
    q, _ = quadrature(window, n)
    t = np.linspace(0, 1, n)
    edges = np.r_[np.c_[x0 + t * (x1 - x0), np.full(n, y0)], np.c_[x0 + t * (x1 - x0), np.full(n, y1)],
                  np.c_[np.full(n, x0), y0 + t * (y1 - y0)], np.c_[np.full(n, x1), y0 + t * (y1 - y0)]]
    return margin * float(max(intensity(q).max(), intensity(edges).max()))


def cell_means(field, g, window, per_side=10):
    """The covariate averaged over each grid cell's part of the window, instead of its value at the centre."""
    x0, x1, y0, y1 = window
    out = []
    for (cx, cy), a in zip(g["centres"], g["area"]):
        half = math.sqrt(a) / 2  # cells cut by the window are averaged over a square of the same area
        sub, _ = quadrature((max(cx - half, x0), min(cx + half, x1), max(cy - half, y0), min(cy + half, y1)),
                            per_side)
        out.append(float(field(sub).mean()))
    return np.array(out)


def simulate_poisson(intensity, window, lam_max, rng):
    x0, x1, y0, y1 = window
    n = rng.poisson(lam_max * (x1 - x0) * (y1 - y0))
    pts = np.c_[rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)]
    if n == 0:
        return pts
    lam = intensity(pts)
    if np.any(lam > lam_max * (1 + 1e-9)):
        raise ValueError("lam_max is below the intensity somewhere: thinning would be wrong")
    return pts[rng.random(n) < lam / lam_max]


def simulate_thomas(kappa, mu, sigma, window, rng):
    x0, x1, y0, y1 = window
    pad = 4 * sigma
    big = (x0 - pad, x1 + pad, y0 - pad, y1 + pad)
    parents = simulate_poisson(lambda xy: np.full(len(xy), float(kappa)), big, float(kappa), rng)
    kids = [p + rng.normal(0, sigma, (rng.poisson(mu), 2)) for p in parents]
    pts = np.vstack(kids) if kids else np.empty((0, 2))
    keep = (pts[:, 0] >= x0) & (pts[:, 0] < x1) & (pts[:, 1] >= y0) & (pts[:, 1] < y1)
    return pts[keep]


def bump_field(window, rng, n_bumps=20, width=0.05):
    x0, x1, y0, y1 = window
    centres = np.c_[rng.uniform(x0, x1, n_bumps), rng.uniform(y0, y1, n_bumps)]
    signs = rng.choice([-1.0, 1.0], n_bumps)
    q, _ = quadrature(window, 100)

    def raw(xy):
        d2 = ((np.asarray(xy, float)[:, None, :] - centres[None]) ** 2).sum(-1)
        return np.exp(-d2 / (2 * width ** 2)) @ signs

    ref = raw(q)
    m, s = ref.mean(), ref.std()
    return lambda xy: (raw(xy) - m) / s


def pearson_dispersion(counts, expected, n_params):
    c, e = np.asarray(counts, float), np.asarray(expected, float)
    return float(np.sum((c - e) ** 2 / e) / (len(c) - n_params))


def mean_nn_distance(points):
    p = np.asarray(points, float)
    if len(p) < 2:
        return float("nan")
    best = np.full(len(p), np.inf)
    for i in range(0, len(p), 500):
        d = np.sqrt(((p[i:i + 500, None] - p[None]) ** 2).sum(-1))
        d[np.arange(d.shape[0]), np.arange(i, i + d.shape[0])] = np.inf
        best[i:i + 500] = d.min(axis=1)
    return float(best.mean())


def monte_carlo_p(observed, simulated, lower=False):
    s = np.asarray(simulated, float)
    k = np.sum(s <= observed) if lower else np.sum(s >= observed)
    return float((k + 1) / (len(s) + 1))


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("x")
    p.add_argument("y")
    p.add_argument("--window", type=float, nargs=4, required=True, metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    p.add_argument("--covariate-x", action="store_true", help="add a linear trend in x (scaled to 0..1)")
    p.add_argument("--cell", type=float, nargs="+", default=[], help="also fit grid Poisson with these cell sizes")
    p.add_argument("--sims", type=int, default=99)
    a = p.parse_args()
    pts = np.array(duckdb.sql(f'select "{a.x}", "{a.y}" from \'{a.table}\'').fetchall(), float)
    x0, x1, y0, y1 = a.window
    inside = (pts[:, 0] >= x0) & (pts[:, 0] < x1) & (pts[:, 1] >= y0) & (pts[:, 1] < y1)
    print(f"points {len(pts)}, inside the window {int(inside.sum())}, area {(x1 - x0) * (y1 - y0):.6g}")
    pts = pts[inside]
    cov = (lambda xy: ((xy[:, 0] - x0) / (x1 - x0))[:, None]) if a.covariate_x else (lambda xy: np.empty((len(xy), 0)))
    q, w = quadrature(a.window, 200)
    fit = fit_poisson_process(cov(pts), cov(q), w)
    names = ["intercept"] + (["x (0..1)"] if a.covariate_x else [])
    for nm, b, s in zip(names, fit["beta"], fit["se"]):
        print(f"  {nm}: {b:.4g} (se {s:.3g})")
    print(f"log-likelihood {fit['loglik']:.6g}")
    lam = lambda xy: np.exp(np.c_[np.ones(len(xy)), cov(xy)] @ fit["beta"])
    rng = np.random.default_rng(0)
    top = intensity_upper(lam, a.window)
    sims = [mean_nn_distance(simulate_poisson(lam, a.window, top, rng)) for _ in range(a.sims)]
    obs = mean_nn_distance(pts)
    print(f"mean nearest-neighbour distance {obs:.4g}; simulated from the fit {np.mean(sims):.4g}; "
          f"p (closer) {monte_carlo_p(obs, sims, lower=True):.3f}. Clustering left over is not proof of "
          "attraction: an unobserved environment makes the same symptom")
    for cell in a.cell:
        g = grid_counts(pts, a.window, cell)
        r = fit_grid_poisson(g["counts"], cov(g["centres"]), g["area"])
        print(f"grid {cell:g}: cells {len(g['counts'])}, zero cells {r['zeros']:.1%}, beta "
              + ", ".join(f"{b:.4g}" for b in r["beta"]))


if __name__ == "__main__":
    main()

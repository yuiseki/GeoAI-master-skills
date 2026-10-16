"""Clustered point patterns as Cox or cluster processes, fitted by minimum contrast on Ripley's K.

    k_function     K(r) estimated as |W| / (n (n - 1)) sum over ordered pairs closer than r of a weight: 1
                   ("none") or the translation correction |W| / |W intersected with W shifted by the pair's
                   offset|, which restores pairs whose partner would fall outside the window
    Thomas         parents Poisson(kappa per unit area), each with Poisson(mu) offspring displaced by a circular
                   Gaussian of sd sigma: K(r) = pi r^2 + (1 - exp(-r^2 / (4 sigma^2))) / kappa. Clustering made
                   by the points (offspring near a parent).
    LGCP           log-Gaussian Cox process: the intensity is exp(Z(s)), Z Gaussian with variance v and an
                   exponential correlation of scale phi. Pair correlation g(r) = exp(v exp(-r / phi)), K(r) =
                   2 pi integral of s g(s) from 0 to r (numerically). Clustering made by an unobserved
                   environment (points independent given Z).
    fit            minimum contrast: minimise the sum over r of (K_hat(r)^q - K_model(r)^q)^2, q = 1/4 (Diggle),
                   over the two parameters (in logs), from a grid of starts. The mean intensity is n / |W|.

Both models have two parameters that set the same thing, how K rises above pi r^2. A pattern made by one is often
fitted as well by the other: K alone cannot tell attraction from environment. Use another source (the order in
time, knowledge of the mechanism, a covariate) to decide. Units are projected; the window is a rectangle.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python cox.py POINTS X Y --window XMIN XMAX YMIN YMAX \\
        --rmax R [--steps 20] [--simulate 39]
"""

import argparse

import numpy as np
from scipy import integrate, optimize


def k_function(x, y, window, rs, correction="translation"):
    x0, x1, y0, y1 = window
    w, h = x1 - x0, y1 - y0
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    dx, dy = x[:, None] - x[None], y[:, None] - y[None]
    d = np.hypot(dx, dy)
    np.fill_diagonal(d, np.inf)
    if correction == "translation":
        e = w * h / ((w - np.abs(dx)) * (h - np.abs(dy)))
    elif correction == "none":
        e = np.ones_like(d)
    else:
        raise ValueError("correction is translation or none")
    return np.array([w * h / (n * (n - 1)) * e[d < r].sum() for r in rs])


def k_thomas(r, kappa, sigma):
    r = np.asarray(r, float)
    return np.pi * r ** 2 + (1 - np.exp(-r ** 2 / (4 * sigma ** 2))) / kappa


def k_lgcp(r, var, scale):
    r = np.atleast_1d(np.asarray(r, float))
    f = lambda s: 2 * np.pi * s * np.exp(var * np.exp(-s / scale))
    return np.array([integrate.quad(f, 0, v, limit=200)[0] for v in r])


MODELS = {"thomas": k_thomas, "lgcp": k_lgcp}


def fit(rs, k_hat, model, area, n, q=0.25):
    """Minimum contrast. Returns the parameters, the contrast, and the parameters in the model's own terms."""
    rs, k_hat = np.asarray(rs, float), np.asarray(k_hat, float)
    kfun = MODELS[model]
    rmax = rs.max()

    def contrast(z):
        a, b = np.exp(z)
        km = kfun(rs, a, b)
        return float(((np.maximum(k_hat, 0) ** q - np.maximum(km, 0) ** q) ** 2).sum())

    if model == "thomas":
        grid = [(k, s) for k in np.array([0.1, 1, 10, 100]) * n / area for s in rmax * np.array([0.02, 0.1, 0.4])]
        bounds = [(1e-3 * n / area, 1e3 * n / area), (1e-3 * rmax, 10 * rmax)]
    else:
        grid = [(v, s) for v in (0.2, 1.0, 3.0) for s in rmax * np.array([0.02, 0.1, 0.4, 1.5])]
        bounds = [(1e-4, 20.0), (1e-3 * rmax, 10 * rmax)]
    lb = np.log([b[0] for b in bounds])
    ub = np.log([b[1] for b in bounds])
    starts = sorted(grid, key=lambda p: contrast(np.log(p)))[:3]
    best = None
    for st in starts:
        r = optimize.minimize(contrast, np.log(st), method="Nelder-Mead", bounds=list(zip(lb, ub)),
                              options={"xatol": 1e-8, "fatol": 1e-14, "maxiter": 4000})
        if best is None or r.fun < best.fun:
            best = r
    a, b = np.exp(best.x)
    edge = bool(np.any(np.abs(best.x - lb) < 1e-3) or np.any(np.abs(best.x - ub) < 1e-3))
    out = {"model": model, "params": (float(a), float(b)), "contrast": float(best.fun), "at_edge": edge}
    lam = n / area
    if model == "thomas":
        out["kappa"], out["sigma"], out["mu"] = float(a), float(b), float(lam / a)
    else:
        out["var"], out["scale"], out["mean_log"] = float(a), float(b), float(np.log(lam) - a / 2)
    return out


def simulate_thomas(kappa, mu, sigma, window, seed=0):
    x0, x1, y0, y1 = window
    rng = np.random.default_rng(seed)
    pad = 4 * sigma
    area = (x1 - x0 + 2 * pad) * (y1 - y0 + 2 * pad)
    if kappa * area * max(mu, 1) > 5e6:
        raise ValueError(f"about {kappa * area * mu:.3g} points: the parameters are not a usable cluster process")
    k = rng.poisson(kappa * area)
    px, py = rng.uniform(x0 - pad, x1 + pad, k), rng.uniform(y0 - pad, y1 + pad, k)
    m = rng.poisson(mu, k)
    x = np.repeat(px, m) + rng.normal(0, sigma, m.sum())
    y = np.repeat(py, m) + rng.normal(0, sigma, m.sum())
    keep = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    return x[keep], y[keep]


def simulate_lgcp(mean_log, var, scale, window, cells=40, seed=0):
    """Z on a cells x cells grid (Cholesky of the exponential covariance), Poisson counts per cell, uniform
    within the cell. The grid must be fine next to scale."""
    x0, x1, y0, y1 = window
    rng = np.random.default_rng(seed)
    cx = x0 + (np.arange(cells) + 0.5) * (x1 - x0) / cells
    cy = y0 + (np.arange(cells) + 0.5) * (y1 - y0) / cells
    GX, GY = np.meshgrid(cx, cy)
    P = np.c_[GX.ravel(), GY.ravel()]
    C = var * np.exp(-np.hypot(P[:, None, 0] - P[None, :, 0], P[:, None, 1] - P[None, :, 1]) / scale)
    Z = mean_log + np.linalg.cholesky(C + 1e-9 * var * np.eye(len(C))) @ rng.normal(size=len(C))
    cell_area = (x1 - x0) * (y1 - y0) / cells ** 2
    counts = rng.poisson(np.exp(Z) * cell_area)
    sx, sy = (x1 - x0) / cells, (y1 - y0) / cells
    x = np.repeat(P[:, 0], counts) + rng.uniform(-sx / 2, sx / 2, counts.sum())
    y = np.repeat(P[:, 1], counts) + rng.uniform(-sy / 2, sy / 2, counts.sum())
    return x, y


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("points")
    p.add_argument("x")
    p.add_argument("y")
    p.add_argument("--where", default="true")
    p.add_argument("--window", type=float, nargs=4, required=True, metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    p.add_argument("--rmax", type=float, required=True, help="largest distance for K; at most a quarter of the "
                                                             "window's shorter side")
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--simulate", type=int, default=0, help="patterns simulated from each fit for an envelope")
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.x}", "{a.y}" from \'{a.points}\' where {a.where}').fetchall()
    x, y = np.array([r[0] for r in rows], float), np.array([r[1] for r in rows], float)
    x0, x1, y0, y1 = a.window
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    x, y = x[inside], y[inside]
    area = (x1 - x0) * (y1 - y0)
    print(f"points {len(rows)}, inside the window {len(x)} (the others are left out); intensity {len(x) / area:.4g}")
    if a.rmax > min(x1 - x0, y1 - y0) / 4:
        print("rmax is beyond a quarter of the window's shorter side: the translation weights grow large there")
    rs = np.linspace(a.rmax / a.steps, a.rmax, a.steps)
    kh = k_function(x, y, a.window, rs)
    L = np.sqrt(kh / np.pi)
    print("L(r) - r (0 under Poisson): " + ", ".join(f"{r:.3g} {l - r:+.3g}" for r, l in zip(rs, L)))
    for model in ("thomas", "lgcp"):
        f = fit(rs, kh, model, area, len(x))
        if model == "thomas":
            desc = f"parents per unit area {f['kappa']:.4g}, offspring per parent {f['mu']:.3g}, sigma {f['sigma']:.4g}"
        else:
            desc = f"variance of log intensity {f['var']:.3g}, scale {f['scale']:.4g}"
        print(f"{model}: {desc}; contrast {f['contrast']:.3g}"
              + ("  (a parameter at its bound: this model does not describe the pattern)" if f["at_edge"] else ""))
        if a.simulate and not f["at_edge"]:
            sims = []
            for s in range(a.simulate):
                if model == "thomas":
                    sx, sy = simulate_thomas(f["kappa"], f["mu"], f["sigma"], a.window, seed=s)
                else:
                    sx, sy = simulate_lgcp(f["mean_log"], f["var"], f["scale"], a.window, seed=s)
                if len(sx) > 1:
                    sims.append(np.sqrt(k_function(sx, sy, a.window, rs) / np.pi) - rs)
            sims = np.array(sims)
            lo, hi = sims.min(0), sims.max(0)
            outside = int(((L - rs < lo) | (L - rs > hi)).sum())
            print(f"  L(r) - r outside the envelope of {len(sims)} simulations at {outside} of {len(rs)} distances")


if __name__ == "__main__":
    main()

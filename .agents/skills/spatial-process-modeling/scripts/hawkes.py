"""A space-time self-exciting (Hawkes) process: events arrive at a background rate and each event raises the
chance of more events soon after and nearby.

    lambda(t, s) = mu / A  +  sum over earlier events i of  K beta exp(-beta (t - t_i)) g(s - s_i)

mu is the background rate per unit time over the window (area A, uniform in space), K the branching ratio (the
mean number of events one event sets off; below 1), beta the decay of triggering in time (1 / beta its mean
delay), g a circular Gaussian of scale sigma. Times are in any unit (days), positions in a projected unit (km).

    simulate               the branching (cluster) construction: background events, then offspring generation by
                           generation; offspring after T or outside the window are dropped
    loglik                 sum of log lambda at the events minus the expected count (the spatial part of each
                           offspring kernel is taken to integrate to 1: offspring falling outside the window are
                           ignored, which biases K down when sigma is not small next to the window)
    fit                    maximum likelihood over (log mu, logit K, log beta, log sigma), and a likelihood ratio test
                           of K = 0 (a plain Poisson process in time, uniform in space)
    background_probability for each event, the chance it came from the background rather than an earlier event

A uniform background is a strong assumption: a place where events happen often for a fixed reason (a front
line, a market) also produces nearby events close in time, and the model reads it as triggering. Model the
background's spatial pattern before reading K as contagion:

    background  mu * f(s) instead of mu / A, f a density over the window. fit(bg=...) takes f fixed;
                fit(bg_mix=g) takes f = (1 - w) / A + w g with the weight w estimated with the rest, g a
                density from earlier events (kde_background: a Gaussian kernel density of bandwidth h,
                normalised to integrate to 1 over the window on a grid). A kernel density alone is lumpy
                where events happen anywhere (a uniform part), and events falling between earlier ones then
                look triggered; the uniform share absorbs that. The compensator is unchanged (f integrates
                to 1). Events of the fitted period must not be used to build g: they would explain
                themselves.
    mean delay  if 1 / beta comes out longer than a fifth of the period, the "triggering" is nearly constant
                in time: it is filling in background the model lacks, not contagion. The likelihood ratio
                test against K = 0 is not calibrated when the background is wrong.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python hawkes.py EVENTS --t COL --x COL --y COL \\
        --window X0 X1 Y0 Y1 --min-sigma PRECISION [--T DAYS] \
        [--background-from EARLIER_EVENTS --background-h H1 H2 ...]
"""

import argparse

import numpy as np
from scipy import stats
from scipy.optimize import minimize


def simulate(mu, K, beta, sigma, T, window, seed=0, background=None):
    """background: a function (rng, n) -> (x, y) drawing the background events' positions (default uniform)."""
    x0, x1, y0, y1 = window
    rng = np.random.default_rng(seed)
    n0 = rng.poisson(mu * T)
    t = rng.uniform(0, T, n0)
    x, y = background(rng, n0) if background else (rng.uniform(x0, x1, n0), rng.uniform(y0, y1, n0))
    bg = np.ones(n0, bool)
    gen = (t, x, y)
    while len(gen[0]):
        k = rng.poisson(K, len(gen[0]))
        pt, px, py = (np.repeat(v, k) for v in gen)
        pt = pt + rng.exponential(1 / beta, len(pt))
        px, py = px + rng.normal(0, sigma, len(px)), py + rng.normal(0, sigma, len(py))
        keep = (pt < T) & (px >= x0) & (px <= x1) & (py >= y0) & (py <= y1)
        gen = (pt[keep], px[keep], py[keep])
        t, x, y = np.r_[t, gen[0]], np.r_[x, gen[1]], np.r_[y, gen[2]]
        bg = np.r_[bg, np.zeros(keep.sum(), bool)]
    o = np.argsort(t)
    return {"t": t[o], "x": x[o], "y": y[o], "is_background": bg[o]}


def _pairs(t, x, y):
    """Every pair (later event j, earlier event i) with t_j > t_i: indices, time differences, squared distances.
    Built once per data set and reused for every likelihood evaluation."""
    t, x, y = (np.asarray(v, float) for v in (t, x, y))
    jj, ii = np.nonzero(t[:, None] > t[None, :])
    return {"j": jj, "dt": t[jj] - t[ii], "d2": (x[jj] - x[ii]) ** 2 + (y[jj] - y[ii]) ** 2, "n": len(t)}


def _trigger_sum(params, pairs):
    _, K, beta, sigma = params
    w = K * beta * np.exp(-beta * pairs["dt"]) * np.exp(-pairs["d2"] / (2 * sigma ** 2)) / (2 * np.pi * sigma ** 2)
    return np.bincount(pairs["j"], weights=w, minlength=pairs["n"])


def _background(bg, n, window):
    x0, x1, y0, y1 = window
    return np.full(n, 1.0 / ((x1 - x0) * (y1 - y0))) if bg is None else np.asarray(bg, float)


def kde_background(px, py, window, h, grid=200):
    """A density over the window from earlier events: f(s) = KDE(s) / integral of KDE over the window. Returns
    a function of (x, y)."""
    px, py = np.asarray(px, float), np.asarray(py, float)
    x0, x1, y0, y1 = window
    gx = x0 + (np.arange(grid) + 0.5) * (x1 - x0) / grid
    gy = y0 + (np.arange(grid) + 0.5) * (y1 - y0) / grid

    def raw(x, y):
        x, y = np.atleast_1d(x), np.atleast_1d(y)
        out = np.empty(len(x))
        for s in range(0, len(x), 2000):
            d2 = (x[s:s + 2000, None] - px[None]) ** 2 + (y[s:s + 2000, None] - py[None]) ** 2
            out[s:s + 2000] = np.exp(-d2 / (2 * h * h)).sum(1) / (2 * np.pi * h * h * len(px))
        return out

    GX, GY = np.meshgrid(gx, gy)
    total = raw(GX.ravel(), GY.ravel()).mean() * (x1 - x0) * (y1 - y0)
    return lambda x, y: raw(x, y) / total


def loglik(params, t, x, y, T, window, pairs=None, bg=None):
    """bg: the background density f at each event (default uniform, 1 / area)."""
    mu, K, beta, sigma = params
    t = np.asarray(t, float)
    pairs = pairs or _pairs(t, x, y)
    lam = mu * _background(bg, len(t), window) + _trigger_sum(params, pairs)
    comp = mu * T + K * (1 - np.exp(-beta * (T - t))).sum()
    return float(np.log(lam).sum() - comp)


def _unpack(z, min_sigma=0.0):
    return np.exp(z[0]), 1 / (1 + np.exp(-z[1])), np.exp(z[2]), min_sigma + np.exp(z[3])


def _mix(z, bg_mix, n, window):
    if bg_mix is None:
        return None
    w = 1 / (1 + np.exp(-z[4]))
    return (1 - w) * _background(None, n, window) + w * np.asarray(bg_mix, float)


def fit(t, x, y, T, window, start=None, min_sigma=0.0, bg=None, bg_mix=None):
    """min_sigma: the smallest spatial scale allowed. Events placed at the same point (a town's centroid) make
    the likelihood grow without bound as sigma goes to 0; set it to the positions' precision."""
    t, x, y = (np.asarray(v, float) for v in (t, x, y))
    if len(t) > 6000:
        raise SystemExit(f"{len(t)} events; the pairs (n^2 / 2) are held in memory, up to 6,000 events")
    if np.any(np.diff(t) < 0):
        raise SystemExit("events must be sorted by time")
    n = len(t)
    pairs = _pairs(t, x, y)
    span = max(window[1] - window[0], window[3] - window[2])
    z0 = start if start is not None else np.array([np.log(0.5 * n / T), 0.0, np.log(10 / T), np.log(span / 20)])
    if bg_mix is not None and len(z0) == 4:
        z0 = np.r_[z0, 0.0]
    same = int((pairs["d2"] == 0).sum())
    best = None
    shifts = [np.array([0, -2, 1, -1]), np.array([0, 1, -1, 1])]
    for zk in [z0] + [z0 + np.r_[d, np.zeros(len(z0) - 4)] for d in shifts]:
        def neg(z):
            v = loglik(_unpack(z, min_sigma), t, x, y, T, window, pairs, _mix(z, bg_mix, n, window) if
                       bg_mix is not None else bg)
            return -v if np.isfinite(v) else np.inf

        r = minimize(neg, zk, method="Nelder-Mead",
                     options={"maxiter": 6000, "xatol": 1e-8, "fatol": 1e-8})
        if best is None or r.fun < best.fun:
            best = r
    params = np.array(_unpack(best.x, min_sigma))
    weight = None
    if bg_mix is not None:
        weight = float(1 / (1 + np.exp(-best.x[4])))
        g = np.asarray(bg_mix, float)
        A = (window[1] - window[0]) * (window[3] - window[2])

        def neg0(v):  # K = 0: mu = n / T, the background weight refitted
            w = 1 / (1 + np.exp(-v[0]))
            return -float(np.log(n / T * ((1 - w) / A + w * g)).sum() - n)

        ll0 = -minimize(neg0, [0.0], method="Nelder-Mead").fun
        bg = (1 - weight) / A + weight * g
    else:
        ll0 = float(np.log(n / T * _background(bg, n, window)).sum()) - n  # K = 0, mu = n / T, the same background
    lr = 2 * (-best.fun - ll0)
    # K = 0 sits on the boundary: the null distribution is half a point mass at 0, half chi^2 with 1 df
    # (beta and sigma are then not identified; this is the usual approximation).
    p = 0.5 * stats.chi2.sf(max(lr, 0), 1) if lr > 0 else 1.0
    return {"params": params, "loglik": -best.fun, "loglik_poisson": ll0, "lr": lr, "lr_test_p": p, "n": n,
            "background_weight": weight, "bg": bg, "delay_too_long": bool(1 / params[2] > T / 5),
            "same_place_pairs": same, "sigma_at_floor": bool(params[3] < min_sigma * 1.01) if min_sigma else False}


def background_probability(params, t, x, y, window, bg=None):
    b = params[0] * _background(bg, len(t), window)
    trig = _trigger_sum(params, _pairs(t, x, y))
    return b / (b + trig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("events")
    p.add_argument("--t", required=True, help="time in days (a number) or a date column")
    p.add_argument("--x", required=True)
    p.add_argument("--y", required=True)
    p.add_argument("--where", default="true")
    p.add_argument("--window", type=float, nargs=4, required=True, metavar=("X0", "X1", "Y0", "Y1"))
    p.add_argument("--T", type=float)
    p.add_argument("--min-sigma", type=float, required=True,
                   help="the positions' precision in the x/y unit; sigma is not allowed below it")
    p.add_argument("--background-from", help="a table of earlier events (same --x, --y columns) whose kernel "
                                             "density is the background's spatial pattern")
    p.add_argument("--background-where", default="true")
    p.add_argument("--background-h", type=float, nargs="+",
                   help="candidate bandwidths of the background density (x/y unit); the best by likelihood is kept")
    a = p.parse_args()
    if bool(a.background_from) != bool(a.background_h):
        p.error("--background-from and --background-h go together")

    import duckdb

    rows = duckdb.sql(f'select "{a.t}", "{a.x}", "{a.y}" from \'{a.events}\' where {a.where}').fetchall()
    tt = np.array([r[0] for r in rows])
    if tt.dtype.kind in "OM":
        tt = np.array([np.datetime64(v, "D") for v in tt])
        tt = (tt - tt.min()).astype(float)
    t, x, y = tt.astype(float), np.array([r[1] for r in rows], float), np.array([r[2] for r in rows], float)
    x0, x1, y0, y1 = a.window
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    o = np.argsort(t[inside], kind="stable")
    t, x, y = t[inside][o], x[inside][o], y[inside][o]
    T = a.T or float(t.max()) + 1
    ties = int((np.diff(t) == 0).sum())
    print(f"events {len(rows)}, inside the window {len(t)}, over {T:g} time units; same-time pairs {ties} "
          "(events at the same time cannot trigger each other here)")
    if a.background_from:
        prev = duckdb.sql(f'select "{a.x}", "{a.y}" from \'{a.background_from}\' where {a.background_where}').fetchall()
        px, py = np.array([r[0] for r in prev], float), np.array([r[1] for r in prev], float)
        keep = (px >= x0) & (px <= x1) & (py >= y0) & (py <= y1)
        print(f"background: uniform mixed with the kernel density of {int(keep.sum())} earlier events inside the window")
        best = None
        for h in a.background_h:
            g = kde_background(px[keep], py[keep], a.window, h)(x, y)
            rh = fit(t, x, y, T, a.window, min_sigma=a.min_sigma, bg_mix=g)
            print(f"  bandwidth {h:g}: log-likelihood {rh['loglik']:.2f}, weight of the density {rh['background_weight']:.2f}, "
                  f"K {rh['params'][1]:.3f}")
            if best is None or rh["loglik"] > best[0]["loglik"]:
                best = (rh, h)
        r, h = best
        print(f"  kept bandwidth {h:g}")
    else:
        r = fit(t, x, y, T, a.window, min_sigma=a.min_sigma)
    bg = r["bg"]
    print(f"pairs of events at the same point: {r['same_place_pairs']}"
          + ("; sigma sits at --min-sigma: the spatial scale is set by the positions' precision, not the data"
             if r["sigma_at_floor"] else ""))
    mu, K, beta, sigma = r["params"]
    print(f"background {mu:.4g} per time unit, branching ratio K {K:.3f}, mean delay {1 / beta:.4g}, "
          f"spatial scale sigma {sigma:.4g}")
    print(f"log-likelihood {r['loglik']:.2f} against a Poisson process {r['loglik_poisson']:.2f}: LR {r['lr']:.1f}, "
          f"p {r['lr_test_p']:.3g}")
    if K > 0.95:
        print("K is at its upper limit (1 means every event replaces itself: an explosive process). The model "
              "explains the data by triggering because nothing else in it can; suspect the background"
              + (" (uniform)" if not a.background_from else ""))
    if r["delay_too_long"]:
        print(f"the mean delay {1 / beta:.4g} is longer than a fifth of the period: the triggering term is nearly "
              "constant in time and fills in background the model lacks; do not read K as contagion")
    pb = background_probability(r["params"], t, x, y, a.window, bg)
    print(f"expected background events {pb.sum():.0f} of {len(t)}; read K as contagion only after the background's "
          "own spatial pattern is modelled")


if __name__ == "__main__":
    main()

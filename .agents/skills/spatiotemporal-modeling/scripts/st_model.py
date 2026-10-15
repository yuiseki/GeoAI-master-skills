"""A small spatio-temporal decomposition, y(s, t) = mu + a(s) + b(t) [+ c(s) (t - tbar)] + residual, fitted by
alternating means over the observed cells (missing location-time cells are fine), with the prediction of
each part where it was not observed, residual diagnostics in space and in time, the four prediction
targets as separate validation splits, and a check of separability.

    models    mean         mu
              space        mu + a(s): a spatial effect per location, nothing in time
              time         mu + b(t): a temporal effect per time, nothing in space
              additive     mu + a(s) + b(t): space and time do not interact
              interaction  additive + c(s) (t - tbar): each location has its own trend (a space-time
                           interaction; the way time changes differs by place)
    new place a(s) and c(s) at a location not in training: the inverse-distance mean of the k nearest
              training locations (k = 4)
    new time  b(t) after the last training time: an AR(1) forecast phi^(gap) x b(last), phi fitted on the
              training b(t) with their own gaps (irregular times allowed); between training times: linear
    splits    random        rows at random (5 folds): every test cell's location and time are in training
              future_known  times after the cutoff at locations seen before it: forecasting
              new_location  held-out locations (5 groups, random or spatial blocks) at the training times
              future_new    held-out locations after the cutoff, trained on the others before it
    diagnostics  spatial: Moran's I of the residuals within each time (4 nearest neighbours), averaged;
              temporal: lag-1 autocorrelation of each location's residuals in time order, pooled
    separability_ratio  C(h, u) C(0, 0) / (C(h, 0) C(0, u)) of the empirical space-time covariance at a
              distance band h and a time lag u (in steps of the sorted distinct times). A separable
              covariance, C(h, u) = Cs(h) Ct(u), gives 1; a field that moves (advection) or a correlation in
              time that differs by place does not. Movement is directional: pass direction (the wind,
              the river) to use only pairs whose later point lies downstream; averaged over all
              directions, the departure from 1 is diluted.
    simulate  worlds: additive (spatial field + AR(1) in time + noise), interaction (additive + a spatially
              smooth trend per location), separable (a field with covariance Cs x Ct), advection (a
              field drifting east by 0.03 per step: non-separable)

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python st_model.py TABLE LOCATION TIME X Y VALUE \\
        --cutoff T [--models mean space time additive interaction] [--blocks]
"""

import argparse

import numpy as np

MODELS = ("mean", "space", "time", "additive", "interaction")


def idw(point, others, values, k=4):
    others, values = np.asarray(others, float), np.asarray(values, float)
    d = np.sqrt(((others - np.asarray(point, float)) ** 2).sum(axis=1))
    near = np.argsort(d)[:k]
    if d[near[0]] == 0:
        return float(values[near[0]])
    w = 1 / d[near]
    return float(np.sum(w * values[near]) / np.sum(w))


def ar1_forecast(last, phi, gap):
    return last * phi ** gap


def fit_phi(times, b):
    times, b = np.asarray(times, float), np.asarray(b, float)
    order = np.argsort(times)
    times, b = times[order], b[order]
    gaps = np.diff(times)
    grid = np.linspace(0, 0.999, 1000)
    loss = [np.sum((b[1:] - p ** gaps * b[:-1]) ** 2) for p in grid]
    best = grid[int(np.argmin(loss))]
    fine = np.linspace(max(best - 0.001, 0), min(best + 0.001, 0.9999), 201)
    loss = [np.sum((b[1:] - p ** gaps * b[:-1]) ** 2) for p in fine]
    return float(fine[int(np.argmin(loss))])


def fit(model, loc, t, y, coords, tol=1e-10, max_iter=10_000):
    if model not in MODELS:
        raise ValueError(f"model is one of {MODELS}")
    loc, t, y = np.asarray(loc), np.asarray(t, float), np.asarray(y, float)
    locs, li = np.unique(loc, return_inverse=True)
    times, ti = np.unique(t, return_inverse=True)
    tbar = float(t.mean())
    a, b, c = np.zeros(len(locs)), np.zeros(len(times)), np.zeros(len(locs))
    mu = float(y.mean())
    use_a = model in ("space", "additive", "interaction")
    use_b = model in ("time", "additive", "interaction")
    use_c = model == "interaction"
    nl, nt = np.bincount(li, minlength=len(locs)), np.bincount(ti, minlength=len(times))
    dt = t - tbar
    for _ in range(max_iter if model != "mean" else 0):
        old = np.r_[a, b, c]
        if use_a:
            a = np.bincount(li, y - mu - b[ti] - c[li] * dt, len(locs)) / nl
        if use_b:
            b = np.bincount(ti, y - mu - a[li] - c[li] * dt, len(times)) / nt
        if use_c:
            r = y - mu - a[li] - b[ti]
            cen = dt - (np.bincount(li, dt, len(locs)) / nl)[li]
            den = np.bincount(li, cen ** 2, len(locs))
            c = np.where(den > 0, np.bincount(li, cen * r, len(locs)) / np.where(den > 0, den, 1), 0)
            a = np.bincount(li, y - mu - b[ti] - c[li] * dt, len(locs)) / nl
        shift = a.mean() + b.mean()
        mu += shift
        a -= a.mean()
        b -= b.mean()
        if np.max(np.abs(np.r_[a, b, c] - old)) < tol:
            break
    phi = fit_phi(times, b) if use_b and len(times) > 2 else 0.0
    return {"model": model, "mu": mu, "a": dict(zip(locs.tolist(), a)), "b": dict(zip(times.tolist(), b)),
            "c": dict(zip(locs.tolist(), c)), "tbar": tbar, "phi": phi,
            "coords": {k: coords[k] for k in locs.tolist()}}


def _place(p, key, s, coords):
    if s in p[key]:
        return p[key][s]
    known = list(p[key])
    return idw(coords[s], [p["coords"][k] for k in known], [p[key][k] for k in known])


def _time(p, t):
    if t in p["b"]:
        return p["b"][t]
    times = np.array(sorted(p["b"]))
    vals = np.array([p["b"][x] for x in times])
    if t > times[-1]:
        return ar1_forecast(vals[-1], p["phi"], t - times[-1])
    if t < times[0]:
        return ar1_forecast(vals[0], p["phi"], times[0] - t)
    return float(np.interp(t, times, vals))


def predict(p, loc, t, coords):
    out = np.full(len(loc), p["mu"])
    m = p["model"]
    for i, (s, tt) in enumerate(zip(np.asarray(loc).tolist(), np.asarray(t, float).tolist())):
        if m in ("space", "additive", "interaction"):
            out[i] += _place(p, "a", s, coords)
        if m in ("time", "additive", "interaction"):
            out[i] += _time(p, tt)
        if m == "interaction":
            out[i] += _place(p, "c", s, coords) * (tt - p["tbar"])
    return out


def moran(z, W):
    z = np.asarray(z, float) - np.mean(z)
    return float(len(z) / W.sum() * (z @ W @ z) / (z @ z))


def knn_weights(points, k=4):
    P = np.asarray(points, float)
    d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    W = np.zeros_like(d)
    for i in range(len(P)):
        W[i, np.argsort(d[i])[:k]] = 1
    return np.maximum(W, W.T)


def lag1_autocorrelation(loc, t, r):
    loc, t, r = np.asarray(loc), np.asarray(t, float), np.asarray(r, float)
    num = den = 0.0
    for s in np.unique(loc):
        m = loc == s
        z = r[m][np.argsort(t[m])]
        z = z - z.mean()
        num += np.sum(z[1:] * z[:-1])
        den += np.sum(z ** 2)
    return float(num / den)


def residual_diagnostics(loc, t, r, coords, k=4):
    loc, t, r = np.asarray(loc), np.asarray(t, float), np.asarray(r, float)
    spatial = []
    for tt in np.unique(t):
        m = t == tt
        if m.sum() > k + 1 and np.std(r[m]) > 0:
            spatial.append(moran(r[m], knn_weights([coords[s] for s in loc[m].tolist()], k)))
    return {"spatial": float(np.mean(spatial)) if spatial else float("nan"),
            "temporal": lag1_autocorrelation(loc, t, r)}


def separability_ratio(loc, t, y, coords, dist, lag, direction=None):
    loc, t, y = np.asarray(loc), np.asarray(t, float), np.asarray(y, float)
    locs = np.unique(loc).tolist()
    times = np.unique(t)
    R = np.full((len(locs), len(times)), np.nan)
    R[[locs.index(s) for s in loc.tolist()], np.searchsorted(times, t)] = y - y.mean()
    P = np.array([coords[s] for s in locs], float)
    d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
    pairs = (d >= dist[0]) & (d < dist[1])
    if direction is not None:  # only pairs whose second point lies within 45 degrees of the direction
        u = np.asarray(direction, float) / np.linalg.norm(direction)
        along = ((P[None] - P[:, None]) @ u) / np.where(d > 0, d, 1)
        pairs &= along > np.cos(np.pi / 4)

    def cov(mask, u):
        A, B = R[:, : R.shape[1] - u], R[:, u:]
        i, j = np.nonzero(mask)
        prod = A[i] * B[j]
        return float(np.nanmean(prod))

    same = np.eye(len(locs), dtype=bool)
    return cov(pairs, lag) * cov(same, 0) / (cov(pairs, 0) * cov(same, lag))


def _groups(locs, coords, blocks, seed, n=5):
    rng = np.random.default_rng(seed)
    locs = np.array(locs)
    if blocks:  # bands of x: spatially contiguous held-out groups
        x = np.array([coords[s][0] for s in locs.tolist()])
        order = locs[np.argsort(x)]
    else:
        order = rng.permutation(locs)
    return [set(g.tolist()) for g in np.array_split(order, n)]


def evaluate(models, loc, t, y, coords, cutoff, seed=0, blocks=False, return_masks=False):
    loc, t, y = np.asarray(loc), np.asarray(t, float), np.asarray(y, float)
    n = len(y)
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(n), 5)
    masks = {"random": [], "future_known": [], "new_location": [], "future_new": []}
    for f in folds:
        test = np.zeros(n, bool)
        test[f] = True
        masks["random"].append((~test, test))
    past = t <= cutoff
    known = set(loc[past].tolist())
    masks["future_known"].append((past, ~past & np.isin(loc, list(known))))
    for g in _groups(np.unique(loc), coords, blocks, seed):
        held = np.isin(loc, list(g))
        masks["new_location"].append((~held, held & np.isin(t, np.unique(t[~held]))))
        masks["future_new"].append((~held & past, held & ~past))
    out = {}
    for kind, pairs in masks.items():
        out[kind] = {}
        for m in models:
            err = []
            for train, test in pairs:
                if test.sum() == 0 or train.sum() == 0:
                    continue
                p = fit(m, loc[train], t[train], y[train], coords)
                err.append(y[test] - predict(p, loc[test], t[test], coords))
            e = np.concatenate(err)
            out[kind][m] = float(np.sqrt(np.mean(e ** 2)))
    if return_masks:
        out["masks"] = masks
    return out


def _exp_cov(P, scale):
    d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
    return np.exp(-d / scale)


def _draw(rng, C):
    return np.linalg.cholesky(C + 1e-9 * np.eye(len(C))) @ rng.normal(size=len(C))


def simulate(world, n_loc=50, n_t=30, seed=0, noise=0.5, missing=0.0, irregular_time=False, phi=0.8):
    rng = np.random.default_rng(seed)
    P = rng.random((n_loc, 2))
    times = np.cumsum(rng.choice([1, 2, 3], n_t)) - 1.0 if irregular_time else np.arange(n_t, dtype=float)
    Ct = phi ** np.abs(times[:, None] - times[None])
    if world in ("additive", "interaction"):
        a = _draw(rng, _exp_cov(P, 0.3))
        b = _draw(rng, Ct)
        Z = a[:, None] + b[None]
        if world == "interaction":
            c = 0.1 * _draw(rng, _exp_cov(P, 0.3))
            Z = Z + c[:, None] * (times - times.mean())[None]
    elif world == "separable":
        Ls = np.linalg.cholesky(_exp_cov(P, 0.3) + 1e-9 * np.eye(n_loc))
        Lt = np.linalg.cholesky(Ct + 1e-9 * np.eye(n_t))
        Z = Ls @ rng.normal(size=(n_loc, n_t)) @ Lt.T
    elif world == "advection":
        v = 0.03
        grid = np.linspace(-v * times.max() - 0.05, 1.05, 400)
        W = _draw(rng, np.exp(-np.abs(grid[:, None] - grid[None]) / 0.2))
        Z = np.array([[np.interp(P[i, 0] - v * tt, grid, W) for tt in times] for i in range(n_loc)])
    else:
        raise ValueError("world is additive, interaction, separable or advection")
    loc = np.repeat(np.arange(n_loc), n_t)
    t = np.tile(times, n_loc)
    y = Z.ravel() + rng.normal(0, noise, n_loc * n_t) if noise else Z.ravel()
    keep = rng.random(len(y)) >= missing
    return {"loc": loc[keep], "t": t[keep], "y": y[keep], "coords": {i: tuple(P[i]) for i in range(n_loc)},
            "n_loc": n_loc, "n_t": n_t}


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("table", "location", "time", "x", "y", "value"):
        p.add_argument(name)
    p.add_argument("--cutoff", type=float, required=True, help="last time used for training in the future splits")
    p.add_argument("--models", nargs="+", default=list(MODELS), choices=MODELS)
    p.add_argument("--blocks", action="store_true", help="hold out bands of x instead of random locations")
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    rows = duckdb.sql(f'select "{a.location}", "{a.time}", "{a.x}", "{a.y}", "{a.value}" from \'{a.table}\'').fetchall()
    rows = [r for r in rows if None not in r]
    loc = np.array([r[0] for r in rows])
    t = np.array([r[1] for r in rows], float)
    y = np.array([r[4] for r in rows], float)
    coords = {}
    for r in rows:
        if coords.setdefault(r[0], (r[2], r[3])) != (r[2], r[3]):
            raise SystemExit(f"location {r[0]} has two positions; one position per location (projected units)")
    n_loc, n_t = len(coords), len(np.unique(t))
    print(f"rows {len(y)}, locations {n_loc}, times {n_t}, cells missing {n_loc * n_t - len(y)} "
          f"({1 - len(y) / (n_loc * n_t):.1%}), time gaps {sorted(set(np.diff(np.unique(t)).tolist()))[:5]}")
    r = evaluate(a.models, loc, t, y, coords, a.cutoff, a.seed, a.blocks)
    print("RMSE by split (rows):  " + "  ".join(f"{m:>11}" for m in a.models))
    for kind, v in r.items():
        print(f"  {kind:<20}" + "  ".join(f"{v[m]:11.4g}" for m in a.models))
    print("residual dependence, all rows fitted: spatial Moran's I, temporal lag-1 autocorrelation")
    for m in a.models:
        fp = fit(m, loc, t, y, coords)
        d = residual_diagnostics(loc, t, y - predict(fp, loc, t, coords), coords)
        print(f"  {m:<12} spatial {d['spatial']:.3f}  temporal {d['temporal']:.3f}")


if __name__ == "__main__":
    main()

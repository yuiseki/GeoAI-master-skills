"""Score interpolation methods on held-out observations, with random and spatially separated splits.

Splits: random (k folds), block (squares of --block-m metres; each fold holds out whole squares), loo (leave
one out), target-distance. The held-out points never stay in their own training set.

target-distance matches the validation geometry to the deployment: it measures, for every prediction point,
the distance to the nearest observation (only the prediction points' coordinates are read, never a value).
Each observation is then held out in turn with its own buffer: a distance d* is drawn from those deployment
distances, and the neighbours closer than the one whose distance is nearest to d* are dropped from its
training set, so the held-out point's nearest training observation lands as close to d* as the network allows
(dropping everything closer than d* overshot: the next station beyond d* is farther on a sparse network).
A network cannot give distances shorter than its own spacing; that shows as a mismatch. The two distance distributions are printed side by side
(n, min, median, mean, p75, p90, max) with their relative differences, and the shares of points outside the
hull (prediction points outside the observations' hull, held-out points outside their training hull). When
the deployment cannot be reproduced, the run says so: with status 2 when the held-out points end up nearer
their training points than the prediction points are (optimistic) or none can be placed, with a warning when
they end up farther (pessimistic). --match-tolerance (default 25 %) is the allowed relative difference of the
median and p90: on a random network the held-out median landed 21 % long, by the network's own spacing. Kriging uses one variogram fitted to all
observations here. Every method is scored on the same rows:
a row that any method could not predict (nothing within --max-dist) is left out for all and counted.

For each method: n, MAE, RMSE, bias (mean of prediction − observed), overall, inside / outside the convex
hull of the training points, by distance to the nearest training point, and for kriging the share of
held-out values inside the nominal 90 % interval (± 1.645 kriging_sd), for ordinary and universal kriging.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyproj --with pyarrow python evaluate_interpolation.py \\
        OBS ID X Y VALUE --crs EPSG:4326 --distance-crs EPSG:32653 --methods mean,nearest,idw,kriging \\
        --split random|block|loo [--folds 10] [--block-m 2500] [--power 2] [--k 12] [--max-dist M]
    ... --split target-distance --prediction-points PRED --prediction-x X --prediction-y Y --prediction-crs CRS
"""

import argparse

import numpy as np

from scipy.spatial import Delaunay, cKDTree
from scipy.stats import wasserstein_distance

from interpolate_points import Obs, audit_duplicates, clean, fit_variogram, predict, project, read_points

BINS = (0, 100, 200, 400, 800, 1600, np.inf)
MATCH_TOLERANCE = 0.25


def read_xy(path, x, y):
    """Coordinates only. A value column at the prediction points is never read."""
    return np.array([[r[0], r[1]] for r in read_points(path, [x, y])], float)


def describe(d):
    d = np.asarray(d, float)
    if not len(d):
        return {"n": 0}
    return {"n": int(len(d)), "min": float(d.min()), "median": float(np.median(d)), "mean": float(d.mean()),
            "p75": float(np.percentile(d, 75)), "p90": float(np.percentile(d, 90)), "max": float(d.max())}


def match(deploy, valid, unscored, n, tol):
    dd, vd = describe(deploy), describe(valid)
    out = {"tolerance": tol, "ok": True, "reason": "", "direction": "matched"}
    if not vd["n"] or unscored > 0.05 * n:
        out.update(ok=False, direction="unreachable",
                   reason=f"{unscored} of {n} held-out points had no training observation near the deployment "
                          "distance: the network cannot reproduce how far the prediction points are")
        return out
    for q in ("median", "p75", "p90"):
        out[f"{q}_relative_difference"] = (vd[q] - dd[q]) / dd[q] if dd[q] else float("inf")
    out["wasserstein_over_median"] = wasserstein_distance(valid, deploy) / dd["median"] if dd["median"] else float("inf")
    bad = [q for q in ("median", "p90") if abs(out[f"{q}_relative_difference"]) > tol]
    if bad:
        short = any(out[f"{q}_relative_difference"] < 0 for q in bad)
        # shorter: held-out points sit nearer their training points than the prediction points do (optimistic);
        # longer: farther (pessimistic), as when the network's own spacing exceeds the deployment distances
        out.update(ok=False, direction="shorter" if short else "longer",
                   reason=f"validation distances are {'shorter' if short else 'longer'} than the deployment at "
                          f"{', '.join(bad)} by more than {tol:.0%}")
    return out


def target_distance(obs, methods, pred_xy, power=2.0, k=12, max_dist=None, seed=0, tol=MATCH_TOLERANCE):
    n = len(obs.v)
    deploy = cKDTree(obs.xy).query(pred_xy, 1)[0]
    try:
        hull = Delaunay(obs.xy)
        deploy_out = float((hull.find_simplex(pred_xy) < 0).mean())
    except Exception:
        deploy_out = 1.0
    d_star = np.random.default_rng(seed).choice(deploy, n)
    vg = fit_variogram(obs.xy, obs.v, "exponential") if "kriging" in methods else None  # universal fits its own
    pred = {m: np.full(n, np.nan) for m in methods}
    sd = {m: np.full(n, np.nan) for m in methods}
    near, inside = np.full(n, np.nan), np.zeros(n, bool)
    for i in range(n):
        dist = np.hypot(*(obs.xy - obs.xy[i]).T)
        dist[i] = np.inf
        # drop the neighbours closer than the one whose distance is nearest to d*: that one becomes the nearest
        # training observation, so the held-out point's distance lands on d* instead of overshooting it
        reach = dist[np.argmin(np.abs(dist - d_star[i]))]
        tr = (dist >= reach) & np.isfinite(dist)
        if not tr.any():
            continue
        train = Obs(obs.xy[tr], obs.v[tr])
        for m in methods:
            r = predict(train, obs.xy[i:i + 1], m, power=power, k=k, max_dist=max_dist,
                        variogram=vg if m == "kriging" else None)
            pred[m][i] = r["prediction"][0]
            near[i], inside[i] = r["nearest_m"][0], r["inside_hull"][0]
            if m in ("kriging", "universal"):
                sd[m][i] = r["kriging_sd"][0]
    return pred, sd, near, inside, deploy, deploy_out


def folds_for(obs, split, folds=10, block_m=2500.0, seed=0):
    n = len(obs.v)
    if split == "loo":
        return np.arange(n)
    if split == "random":
        return np.random.default_rng(seed).permutation(n) % folds
    if split == "block":
        b = np.floor((obs.xy - obs.xy.min(0)) / block_m).astype(int)
        keys = {k: i for i, k in enumerate(sorted(set(map(tuple, b))))}
        return np.array([keys[tuple(x)] for x in b])
    raise SystemExit("--split must be random, block or loo")


def summary(err, mask):
    e = err[mask]
    if not len(e):
        return {"n": 0}
    return {"n": int(len(e)), "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean())}


def evaluate(obs, methods, split="random", folds=10, block_m=2500.0, power=2.0, k=12, max_dist=None, seed=0,
             pred_xy=None, match_tolerance=MATCH_TOLERANCE):
    n = len(obs.v)
    if split == "target-distance":
        if pred_xy is None:
            raise SystemExit("--split target-distance needs the prediction points")
        pred, sd, near, inside, deploy, deploy_out = target_distance(obs, methods, pred_xy, power, k, max_dist, seed,
                                                                     match_tolerance)
        return score(obs, methods, split, pred, sd, near, inside, deploy, deploy_out, match_tolerance)
    f = folds_for(obs, split, folds, block_m, seed)
    pred = {m: np.full(n, np.nan) for m in methods}
    sd = {m: np.full(n, np.nan) for m in methods}
    near = np.full(n, np.nan)
    inside = np.zeros(n, bool)
    for g in np.unique(f):
        te, tr = f == g, f != g
        if tr.sum() == 0:
            continue
        train = Obs(obs.xy[tr], obs.v[tr])
        for m in methods:
            r = predict(train, obs.xy[te], m, power=power, k=k, max_dist=max_dist)
            pred[m][te] = r["prediction"]
            near[te], inside[te] = r["nearest_m"], r["inside_hull"]
            if m in ("kriging", "universal"):
                sd[m][te] = r["kriging_sd"]
    deploy = cKDTree(obs.xy).query(pred_xy, 1)[0] if pred_xy is not None else None
    return score(obs, methods, split, pred, sd, near, inside, deploy, None, match_tolerance)


def score(obs, methods, split, pred, sd, near, inside, deploy, deploy_out, tol):
    n = len(obs.v)
    scored = np.all([~np.isnan(pred[m]) for m in methods], axis=0)
    out = {"split": split, "rows": n, "unscored": int((~scored).sum()),
           "distances": {"validation": near[scored], "deployment": deploy},
           "hull": {"validation_outside": float((~inside[scored]).mean()) if scored.any() else None,
                    "deployment_outside": deploy_out}}
    if deploy is not None:
        out["match"] = match(deploy, near[scored], int((~scored).sum()), n, tol)
    for m in methods:
        err = pred[m] - obs.v
        r = {"all": summary(err, scored), "inside_hull": summary(err, scored & inside),
             "outside_hull": summary(err, scored & ~inside)}
        for lo, hi in zip(BINS[:-1], BINS[1:]):
            r[f"nearest_{lo:g}-{hi:g}m"] = summary(err, scored & (near >= lo) & (near < hi))
        if m in ("kriging", "universal"):
            ok = scored & ~np.isnan(sd[m])
            r["coverage_90"] = float((np.abs(err[ok]) <= 1.645 * sd[m][ok]).mean()) if ok.any() else None
        out[m] = r
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("obs", "obs_id", "x", "y", "value"):
        p.add_argument(a)
    p.add_argument("--crs", required=True)
    p.add_argument("--distance-crs", required=True)
    p.add_argument("--methods", default="mean,nearest,idw")
    p.add_argument("--split", default="block", choices=("random", "block", "loo", "target-distance"))
    p.add_argument("--prediction-points", help="where the values will be predicted (coordinates only are read)")
    p.add_argument("--prediction-x")
    p.add_argument("--prediction-y")
    p.add_argument("--prediction-crs")
    p.add_argument("--match-tolerance", type=float, default=MATCH_TOLERANCE)
    p.add_argument("--folds", type=int, default=10)
    p.add_argument("--block-m", type=float, default=2500.0)
    p.add_argument("--power", type=float, default=2.0)
    p.add_argument("--k", type=int, default=12)
    p.add_argument("--max-dist", type=float)
    p.add_argument("--duplicates", default="error", choices=("error", "mean"))
    a = p.parse_args()
    rows = read_points(a.obs, [a.obs_id, a.x, a.y, a.value])
    xy = np.array([[r[1], r[2]] for r in rows], float)
    v = np.array([np.nan if r[3] is None else r[3] for r in rows], float)
    o, rep = clean(project(xy, a.crs, a.distance_crs), v)
    o, drep = audit_duplicates(o.xy, o.v, a.duplicates)
    print(f"observations {len(rows)}, missing {rep['missing_values']}, locations {drep['locations']}, "
          f"conflicting {drep['conflicting_locations']}")
    pred_xy = None
    if a.prediction_points:
        pred_xy = project(read_xy(a.prediction_points, a.prediction_x, a.prediction_y), a.prediction_crs or a.crs,
                          a.distance_crs)
    r = evaluate(o, a.methods.split(","), a.split, a.folds, a.block_m, a.power, a.k, a.max_dist,
                 pred_xy=pred_xy, match_tolerance=a.match_tolerance)
    print(f"split {r['split']}: rows {r['rows']}, unscored {r['unscored']}")
    if r["distances"]["deployment"] is not None:
        dd, vd = describe(r["distances"]["deployment"]), describe(r["distances"]["validation"])
        print(f"{'nearest-observation distance (m)':34s} {'prediction->observation':>24s} {'validation->training':>22s}")
        for q in ("n", "min", "median", "mean", "p75", "p90", "max"):
            print(f"{q:34s} {dd.get(q, float('nan')):24.1f} {vd.get(q, float('nan')):22.1f}")
        h = r["hull"]
        print(f"outside the hull: prediction points {h['deployment_outside']}, held-out points {h['validation_outside']}")
        if "match" in r:
            print("match: " + ", ".join(f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}" for k, v in r["match"].items()))
    for m in a.methods.split(","):
        for part, s in r[m].items():
            if isinstance(s, dict) and s.get("n"):
                print(f"{m:8s} {part:22s} n {s['n']:5d}  MAE {s['mae']:9.3f}  RMSE {s['rmse']:9.3f}  bias {s['bias']:8.3f}")
        if "coverage_90" in r[m]:
            print(f"{m:8s} coverage of the nominal 90 % interval: {r[m]['coverage_90']}")
    if "match" in r and not r["match"]["ok"]:
        if r["match"]["direction"] in ("shorter", "unreachable"):
            raise SystemExit(f"the validation does not reproduce the deployment: {r['match']['reason']}")
        print(f"warning: {r['match']['reason']}; the error estimates lean pessimistic")


if __name__ == "__main__":
    main()

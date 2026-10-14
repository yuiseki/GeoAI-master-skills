"""Score interpolation methods on held-out observations, with random and spatially separated splits.

Splits: random (k folds), block (squares of --block-m metres; each fold holds out whole squares), loo (leave
one out). The held-out points never stay in their own training set. Every method is scored on the same rows:
a row that any method could not predict (nothing within --max-dist) is left out for all and counted.

For each method: n, MAE, RMSE, bias (mean of prediction − observed), overall, inside / outside the convex
hull of the training points, by distance to the nearest training point, and for kriging the share of
held-out values inside the nominal 90 % interval (± 1.645 kriging_sd).

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyproj --with pyarrow python evaluate_interpolation.py \\
        OBS ID X Y VALUE --crs EPSG:4326 --distance-crs EPSG:32653 --methods mean,nearest,idw,kriging \\
        --split random|block|loo [--folds 10] [--block-m 2500] [--power 2] [--k 12] [--max-dist M]
"""

import argparse

import numpy as np

from interpolate_points import Obs, audit_duplicates, clean, predict, project, read_points

BINS = (0, 100, 200, 400, 800, 1600, np.inf)


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


def evaluate(obs, methods, split="random", folds=10, block_m=2500.0, power=2.0, k=12, max_dist=None, seed=0):
    f = folds_for(obs, split, folds, block_m, seed)
    n = len(obs.v)
    pred = {m: np.full(n, np.nan) for m in methods}
    sd = np.full(n, np.nan)
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
            if m == "kriging":
                sd[te] = r["kriging_sd"]
    scored = np.all([~np.isnan(pred[m]) for m in methods], axis=0)
    out = {"split": split, "rows": n, "unscored": int((~scored).sum())}
    for m in methods:
        err = pred[m] - obs.v
        r = {"all": summary(err, scored), "inside_hull": summary(err, scored & inside),
             "outside_hull": summary(err, scored & ~inside)}
        for lo, hi in zip(BINS[:-1], BINS[1:]):
            r[f"nearest_{lo:g}-{hi:g}m"] = summary(err, scored & (near >= lo) & (near < hi))
        if m == "kriging":
            ok = scored & ~np.isnan(sd)
            r["coverage_90"] = float((np.abs(err[ok]) <= 1.645 * sd[ok]).mean()) if ok.any() else None
        out[m] = r
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("obs", "obs_id", "x", "y", "value"):
        p.add_argument(a)
    p.add_argument("--crs", required=True)
    p.add_argument("--distance-crs", required=True)
    p.add_argument("--methods", default="mean,nearest,idw")
    p.add_argument("--split", default="block", choices=("random", "block", "loo"))
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
    r = evaluate(o, a.methods.split(","), a.split, a.folds, a.block_m, a.power, a.k, a.max_dist)
    print(f"split {r['split']}: rows {r['rows']}, unscored {r['unscored']}")
    for m in a.methods.split(","):
        for part, s in r[m].items():
            if isinstance(s, dict) and s.get("n"):
                print(f"{m:8s} {part:22s} n {s['n']:5d}  MAE {s['mae']:9.3f}  RMSE {s['rmse']:9.3f}  bias {s['bias']:8.3f}")
        if "coverage_90" in r[m]:
            print(f"{m:8s} coverage of the nominal 90 % interval: {r[m]['coverage_90']}")


if __name__ == "__main__":
    main()

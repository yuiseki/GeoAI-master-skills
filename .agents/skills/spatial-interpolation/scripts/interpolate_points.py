"""Estimate a continuous value at unobserved points from the values observed at other points.

Methods (all on distances in metres in a projected CRS; a geographic CRS is refused):
    mean      the mean of the observations (the baseline that ignores space)
    nearest   the value of the nearest observation
    knn       the mean of the --k nearest observations
    idw       inverse distance weighting over the --k nearest within --max-dist: Σ v_i d_i^-p / Σ d_i^-p.
              A query on an observation takes its value (no division by zero).
    kriging   ordinary kriging over the --k nearest, with a variogram (exponential or spherical) fitted to the
              observations by weighted least squares, or given as --variogram MODEL NUGGET SILL RANGE.
              Also returns kriging_sd, the model's standard deviation; check its coverage on held-out points
              before reading it as an interval.
    universal universal kriging over the --k nearest with a linear drift in x and y (the mean is a + b x + c y,
              its coefficients unknown and filtered out by constraints: the weights sum to 1 and reproduce the
              query's x and y). The variogram is fitted to the residuals of a least-squares plane over all
              observations (a regression-kriging residual variogram; biased low at long lags) unless given.
              A plane extrapolates: outside the hull the prediction follows the trend instead of returning to
              the mean, which is right only if the trend continues there.
    --anisotropy ANGLE RATIO (or auto): both krigings on geometrically anisotropic distances; the variogram's
              range is then the range along ANGLE. auto picks (angle, ratio) on a grid (every 15 degrees; ratios
              1 to 6) by leave-one-out kriging error on a sample of 400 observations.

Every prediction point gets a row: prediction (NaN with status no_neighbors when nothing is within
--max-dist), nearest_m (distance to the nearest observation), n_used, inside_hull (inside the convex hull of
the observations: interpolation; outside: extrapolation).

Observations with a missing value are dropped and counted. Observations at the same coordinates are audited:
identical values are kept once; disagreeing values stop the run (--duplicates error) or are averaged
(--duplicates mean), and the counts are printed. Select one time or period before calling this.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyproj --with pyarrow python interpolate_points.py \\
        OBS ID X Y VALUE --crs EPSG:4326 --distance-crs EPSG:32653 PRED PRED_ID PRED_X PRED_Y \\
        --method idw [--power 2] [--k 12] [--max-dist M] [--duplicates error|mean] [--pred-crs CRS] --out out.parquet
"""

import argparse
import sys
from dataclasses import dataclass

import numpy as np
import pyproj
from scipy.optimize import least_squares
from scipy.spatial import Delaunay, cKDTree

METHODS = ("mean", "nearest", "knn", "idw", "kriging", "universal")


@dataclass
class Obs:
    xy: np.ndarray
    v: np.ndarray


def project(xy, src, dst):
    if pyproj.CRS(dst).is_geographic:
        raise SystemExit(f"--distance-crs {dst} is geographic: degrees are not distances. Use a projected CRS in metres")
    tr = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    return np.column_stack(tr.transform(xy[:, 0], xy[:, 1]))


def clean(xy, v):
    ok = ~np.isnan(v)
    return Obs(xy[ok], v[ok]), {"missing_values": int((~ok).sum())}


def audit_duplicates(xy, v, policy="error"):
    keys = {}
    for i, (x, y) in enumerate(xy):
        keys.setdefault((x, y), []).append(i)
    same, conflict, out_xy, out_v = 0, [], [], []
    for (x, y), idx in keys.items():
        vals = v[idx]
        if len(idx) > 1 and np.all(vals == vals[0]):
            same += 1
        elif len(idx) > 1:
            conflict.append(((x, y), vals.tolist()))
        out_xy.append((x, y))
        out_v.append(vals.mean())
    rep = {"rows": len(v), "locations": len(keys), "same_value_duplicates": same, "conflicting_locations": len(conflict)}
    if conflict and policy == "error":
        raise SystemExit(f"{len(conflict)} locations hold disagreeing values, e.g. {conflict[:3]}. "
                         "Choose one time, fix them, or pass --duplicates mean")
    return Obs(np.array(out_xy, float), np.array(out_v, float)), rep


def gamma(h, model, nugget, sill, rng):
    h = np.asarray(h, float)
    part = sill - nugget
    if model == "exponential":
        g = nugget + part * (1 - np.exp(-h / rng))
    elif model == "spherical":
        r = np.minimum(h / rng, 1.0)
        g = nugget + part * (1.5 * r - 0.5 * r ** 3)
    else:
        raise SystemExit("variogram model must be exponential or spherical")
    return np.where(h > 0, g, 0.0)


def kriging_variance_single(d, model, nugget, sill, rng):
    """Ordinary kriging variance with one observation at distance d: weight 1, Lagrange multiplier gamma(d)."""
    return float(2 * gamma(d, model, nugget, sill, rng))


def empirical_variogram(xy, v, n_lags=15, max_lag=None, max_pairs=200_000, seed=0):
    n = len(v)
    i, j = np.triu_indices(n, 1)
    if len(i) > max_pairs:
        pick = np.random.default_rng(seed).choice(len(i), max_pairs, replace=False)
        i, j = i[pick], j[pick]
    d = np.hypot(*(xy[i] - xy[j]).T)
    sv = 0.5 * (v[i] - v[j]) ** 2
    max_lag = max_lag or d.max() / 2
    edges = np.linspace(0, max_lag, n_lags + 1)
    b = np.digitize(d, edges) - 1
    keep = (b >= 0) & (b < n_lags)
    cnt = np.bincount(b[keep], minlength=n_lags)
    mean_d = np.bincount(b[keep], d[keep], n_lags) / np.maximum(cnt, 1)
    mean_g = np.bincount(b[keep], sv[keep], n_lags) / np.maximum(cnt, 1)
    ok = cnt > 0
    return mean_d[ok], mean_g[ok], cnt[ok]


def fit_variogram(xy, v, model="exponential"):
    """Weighted least squares (weights = pairs per lag) of nugget, partial sill and range."""
    h, g, cnt = empirical_variogram(xy, v)
    var = float(np.var(v))
    w = np.sqrt(cnt)

    def resid(p):
        return w * (gamma(h, model, p[0], p[0] + p[1], p[2]) - g)

    lo = [0.0, 0.0, max(h.min() / 3, 1e-9)]
    hi = [2 * var + 1e-12, 2 * var + 1e-12, h.max() * 3]
    p = least_squares(resid, [0.1 * var, 0.9 * var, h.max() / 3], bounds=(lo, hi)).x
    return model, float(p[0]), float(p[0] + p[1]), float(p[2])


def _hull(xy):
    try:
        return Delaunay(xy)
    except Exception:
        return None


def anisotropic(xy, angle_deg, ratio):
    """Geometric anisotropy as PyKrige writes it: rotate by -angle (degrees, counter-clockwise from east), then
    stretch the rotated y by ratio. Correlation then reaches ratio times farther along the angle's direction
    than across it. Distances in the result are the anisotropic distances."""
    a = np.radians(angle_deg)
    c, s_ = np.cos(-a), np.sin(-a)
    xy = np.asarray(xy, float)
    return np.c_[c * xy[:, 0] - s_ * xy[:, 1], ratio * (s_ * xy[:, 0] + c * xy[:, 1])]


def estimate_anisotropy(xy, v, angles=tuple(range(0, 180, 15)), ratios=(1.0, 1.5, 2.0, 3.0, 4.0, 6.0), k=12,
                        sample=400, seed=0):
    """The (angle, ratio) whose ordinary kriging predicts left-out observations best: for each candidate, the
    coordinates are transformed (anisotropic()), a variogram is fitted, and every observation of a sample is
    predicted from the others (leave one out). Ranges fitted to directional variograms were too noisy to pick
    a direction (references/kriging.md)."""
    xy, v = np.asarray(xy, float), np.asarray(v, float)
    rng = np.random.default_rng(seed)
    test = rng.choice(len(v), min(sample, len(v)), replace=False)
    scores = {}
    for ratio in ratios:
        for angle in (angles if ratio != 1.0 else (0,)):
            a = anisotropic(xy, angle, ratio)
            vg = fit_variogram(a, v, "exponential")
            tree = cKDTree(a)
            _, idx = tree.query(a[test], k + 1)
            err = []
            for t, nb in zip(test, idx):
                nb = nb[nb != t][:k]
                p = predict(Obs(a[nb], v[nb]), a[t:t + 1], "kriging", k=k, variogram=vg)["prediction"][0]
                err.append(p - v[t])
            scores[(float(angle), float(ratio))] = float(np.sqrt(np.mean(np.square(err))))
    best = min(scores, key=scores.get)
    return {"angle": best[0], "ratio": best[1], "rmse": scores[best], "isotropic_rmse": scores[(0.0, 1.0)],
            "scores": scores}


def predict(obs, qxy, method, power=2.0, k=12, max_dist=None, variogram=None, anisotropy=None):
    """anisotropy (angle, ratio): kriging and universal kriging on anisotropic distances (anisotropic()); the
    neighbours are chosen by them too. nearest_m and inside_hull stay in the original metres."""
    if method not in METHODS:
        raise SystemExit(f"--method must be one of {METHODS}")
    if anisotropy is not None and method in ("kriging", "universal"):
        res = predict(Obs(anisotropic(obs.xy, *anisotropy), obs.v), anisotropic(qxy, *anisotropy), method, power,
                      k, None, variogram)
        plain = predict(obs, qxy, "nearest", max_dist=max_dist)
        far = plain["status"] == "no_neighbors"
        res["prediction"][far] = np.nan
        res["kriging_sd"][far] = np.nan
        res["status"] = plain["status"]
        res["nearest_m"], res["inside_hull"] = plain["nearest_m"], plain["inside_hull"]
        res["anisotropy"] = anisotropy
        return res
    n = len(obs.v)
    tree = cKDTree(obs.xy)
    kk = 1 if method == "nearest" else min(k, n)
    d, idx = tree.query(qxy, kk)
    d, idx = d.reshape(len(qxy), -1), idx.reshape(len(qxy), -1)
    nearest = d[:, 0]
    reach = np.ones_like(d, bool) if max_dist is None else d <= max_dist
    hull = _hull(obs.xy)
    inside = hull.find_simplex(qxy) >= 0 if hull is not None else np.zeros(len(qxy), bool)
    pred = np.full(len(qxy), np.nan)
    sd = np.full(len(qxy), np.nan)
    used = reach.sum(1) if method != "mean" else np.full(len(qxy), n)
    if method == "kriging" and variogram is None:
        variogram = fit_variogram(obs.xy, obs.v, "exponential")
    centre, scale = obs.xy.mean(0), max(float(obs.xy.std(0).max()), 1e-12)  # drift columns on a unit scale
    if method == "universal" and variogram is None:
        F = np.c_[np.ones(n), (obs.xy - centre) / scale]
        trend = F @ np.linalg.lstsq(F, obs.v, rcond=None)[0]
        variogram = fit_variogram(obs.xy, obs.v - trend, "exponential")
    for q in range(len(qxy)):
        r = reach[q]
        if method == "mean":
            pred[q] = obs.v.mean()
            continue
        if not r.any():
            continue
        dq, vq = d[q][r], obs.v[idx[q][r]]
        if method in ("nearest", "knn"):
            pred[q] = vq.mean() if method == "knn" else vq[0]
        elif method == "idw":
            zero = dq == 0
            pred[q] = vq[zero].mean() if zero.any() else np.sum(vq * dq ** -power) / np.sum(dq ** -power)
        else:
            m, nug, sill, rng = variogram
            pts = obs.xy[idx[q][r]]
            m_ = len(vq)
            # drift columns: the constant (ordinary kriging), plus x and y (universal)
            F = np.ones((m_, 1)) if method == "kriging" else np.c_[np.ones(m_), (pts - centre) / scale]
            f0 = np.ones(1) if method == "kriging" else np.r_[1.0, (qxy[q] - centre) / scale]
            p_ = F.shape[1]
            A = np.zeros((m_ + p_, m_ + p_))
            A[:m_, :m_] = gamma(np.hypot(*(pts[:, None, :] - pts[None, :, :]).transpose(2, 0, 1)), m, nug, sill, rng)
            A[:m_, m_:] = F
            A[m_:, :m_] = F.T
            b = np.r_[gamma(dq, m, nug, sill, rng), f0]
            sol = np.linalg.lstsq(A, b, rcond=None)[0]
            lam, mu = sol[:m_], sol[m_:]
            pred[q] = float(lam @ vq)
            sd[q] = float(np.sqrt(max(lam @ b[:m_] + mu @ f0, 0.0)))
    status = np.where(np.isnan(pred), "no_neighbors", "ok")
    out = {"prediction": pred, "nearest_m": nearest, "n_used": used, "inside_hull": inside, "status": status}
    if method in ("kriging", "universal"):
        out["kriging_sd"] = sd
        out["variogram"] = variogram
    return out


def read_points(path, cols):
    import duckdb
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs;")
    sel = ", ".join(f"\"{c}\"" for c in cols)
    return con.sql(f"select {sel} from '{path}'").fetchall()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("obs", "obs_id", "x", "y", "value"):
        p.add_argument(a)
    p.add_argument("--crs", required=True)
    p.add_argument("--distance-crs", required=True)
    for a in ("pred", "pred_id", "pred_x", "pred_y"):
        p.add_argument(a)
    p.add_argument("--pred-crs")
    p.add_argument("--method", required=True, choices=METHODS)
    p.add_argument("--power", type=float, default=2.0)
    p.add_argument("--k", type=int, default=12)
    p.add_argument("--max-dist", type=float)
    p.add_argument("--variogram", nargs=4, metavar=("MODEL", "NUGGET", "SILL", "RANGE"))
    p.add_argument("--anisotropy", nargs="+", metavar="ANGLE RATIO | auto",
                   help="kriging: the direction of longest correlation (degrees counter-clockwise from east) and the "
                        "ratio of the longest to the shortest range; 'auto' estimates both from directional variograms")
    p.add_argument("--duplicates", default="error", choices=("error", "mean"))
    p.add_argument("--out", required=True)
    a = p.parse_args()
    rows = read_points(a.obs, [a.obs_id, a.x, a.y, a.value])
    xy = np.array([[r[1], r[2]] for r in rows], float)
    v = np.array([np.nan if r[3] is None else r[3] for r in rows], float)
    exact = len(rows) - len(set(rows))
    o, rep = clean(project(xy, a.crs, a.distance_crs), v)
    o, drep = audit_duplicates(o.xy, o.v, a.duplicates)
    q = read_points(a.pred, [a.pred_id, a.pred_x, a.pred_y])
    qxy = project(np.array([[r[1], r[2]] for r in q], float), a.pred_crs or a.crs, a.distance_crs)
    vg = (a.variogram[0], *map(float, a.variogram[1:])) if a.variogram else None
    aniso = None
    if a.anisotropy:
        if a.anisotropy == ["auto"]:
            est = estimate_anisotropy(o.xy, o.v, k=a.k)
            aniso = (est["angle"], est["ratio"])
            print(f"anisotropy chosen by leave-one-out kriging: angle {est['angle']:g}, ratio {est['ratio']:g}; "
                  f"RMSE {est['rmse']:.4g} against {est['isotropic_rmse']:.4g} isotropic")
        else:
            aniso = (float(a.anisotropy[0]), float(a.anisotropy[1]))
    res = predict(o, qxy, a.method, a.power, a.k, a.max_dist, vg, aniso)
    import pyarrow as pa
    import pyarrow.parquet as pq
    cols = {"id": [r[0] for r in q], "prediction": [None if np.isnan(x) else float(x) for x in res["prediction"]],
            "nearest_m": res["nearest_m"].tolist(), "n_used": res["n_used"].tolist(),
            "inside_hull": res["inside_hull"].tolist(), "status": res["status"].tolist(), "method": [a.method] * len(q)}
    if "kriging_sd" in res:
        cols["kriging_sd"] = [None if np.isnan(x) else float(x) for x in res["kriging_sd"]]
        print(f"variogram: {res['variogram']}")
    pq.write_table(pa.table(cols), a.out)
    print(f"observations: {len(rows)}  exact duplicate rows: {exact}  missing values: {rep['missing_values']}  "
          f"locations: {drep['locations']}  same-value duplicates: {drep['same_value_duplicates']}  "
          f"conflicting: {drep['conflicting_locations']}")
    print(f"predictions: {len(q)}  no_neighbors: {int((res['status'] == 'no_neighbors').sum())}  "
          f"outside hull: {int((~res['inside_hull']).sum())}")


if __name__ == "__main__":
    main()

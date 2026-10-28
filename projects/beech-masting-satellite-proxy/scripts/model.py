"""Models, splits and scores of EXPERIMENT_PLAN.md (site x target year t, rank 0-3, Landsat 5 anomalies).

Rows carry: ID, t, y (rank at t), lag_own (rank at t - 1, NaN if missing), dT, x and y_m (EPSG:6691 metres).
raw carries the seasonal satellite values per site and target year: ID, t, ndvi_ps, ndmi_ps (previous summer,
July-August of t - 1), ndvi_cs, ndmi_cs (current spring, April-May of t); NaN where the coverage rule fails.

The splits, the 50 km blocks, the 15 km buffer, the seeds and the neighbour lag are copied unchanged from
projects/beech-masting-spatial-proxy/scripts/model.py:

    A  unknown year: leave one target year out; training drops years t and t + 1 (t + 1 carries t as its lag)
    B  unknown site: 50 km blocks -> 5 folds at random (repeat r uses seed r), sites within 15 km of a test site
       are left out of training; every year is on both sides
    C  unknown site and year: fold f x year t; training = sites outside f and its buffer, years other than t, t + 1

Satellite anomalies: value minus the site's mean over the fold's climatology years (A and C: the training years
without t and t + 1; B: every training year, leaving out each row's own year). A site needs min_years values in
those years, otherwise the anomaly is missing. Within a run every model is fitted and scored on the same rows, the
rows with all four anomalies. All models are least squares with an intercept, predictions clipped to 0-3.
"""

import math

import numpy as np
import pandas as pd

K_NEAR = 5
BLOCK_M = 50_000.0
BUFFER_M = 15_000.0
FOLDS = 5
REPEATS = 10
MIN_ROWS_PER_YEAR = 10
SAT = ["ndvi_ps", "ndmi_ps", "ndvi_cs", "ndmi_cs"]
FEATURES = {
    "B0": ["lag", "dT"],
    "R0": ["dT"],
    "S1": ["lag", "dT", "ndvi_ps", "ndmi_ps"],
    "S2": ["lag", "dT"] + SAT,
    "RS2": ["dT"] + SAT,
}


def fit_predict(train, test, model):
    cols = FEATURES[model]
    Xtr = np.column_stack([np.ones(len(train))] + [train[c].to_numpy(float) for c in cols])
    Xte = np.column_stack([np.ones(len(test))] + [test[c].to_numpy(float) for c in cols])
    beta, *_ = np.linalg.lstsq(Xtr, train.y.to_numpy(float), rcond=None)
    return np.clip(Xte @ beta, 0.0, 3.0)


# ---- satellite anomalies ----

def anomalies(raw, clim_years, min_years, leave_own_year=False):
    """raw (ID, t, SAT) -> the same rows with each SAT value minus the site's mean over clim_years (NaN if the
    site has fewer than min_years values there; with leave_own_year the row's own year is left out)."""
    clim_years = set(clim_years)
    out = raw[["ID", "t"]].copy()
    in_clim = raw.t.isin(clim_years).to_numpy()
    for c in SAT:
        v = raw[c].to_numpy(float)
        use = in_clim & ~np.isnan(v)
        s = pd.Series(np.where(use, v, 0.0)).groupby(raw.ID.to_numpy()).transform("sum").to_numpy()
        n = pd.Series(use.astype(float)).groupby(raw.ID.to_numpy()).transform("sum").to_numpy()
        if leave_own_year:
            s, n = s - np.where(use, v, 0.0), n - use
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(n >= min_years, s / np.maximum(n, 1), np.nan)
        out[c] = v - mean
    return out


def site_permutation(raw, rng):
    """F2: within each year, the four anomalies of a site are replaced by those of another site of the same year
    (among the sites with all four raw values that year). Returns transform(anomaly table) -> table."""
    src = {}
    ok = raw.dropna(subset=SAT)
    for t, g in ok.groupby("t"):
        ids = g.ID.to_numpy()
        src.update({(i, t): j for i, j in zip(ids, rng.permutation(ids))})

    def tf(an):
        a = an.set_index(["ID", "t"])
        keys = list(zip(an.ID, an.t))
        take = [src.get(k, (None,)) for k in keys]
        new = an.copy()
        idx = [(j, k[1]) if j != (None,) else k for j, k in zip(take, keys)]
        new[SAT] = a.reindex(pd.MultiIndex.from_tuples(idx))[SAT].to_numpy()
        return new

    return tf


def year_permutation(years, rng):
    """F1: every site's anomalies of year t are replaced by its anomalies of year pi(t) (one pi for all sites)."""
    years = list(years)
    pi = dict(zip(years, rng.permutation(years)))

    def tf(an):
        a = an.set_index(["ID", "t"])
        idx = pd.MultiIndex.from_arrays([an.ID.to_numpy(), an.t.map(lambda t: pi.get(t, t)).to_numpy()])
        new = an.copy()
        new[SAT] = a.reindex(idx)[SAT].to_numpy()
        return new

    return tf


def with_anomalies(sub, raw, clim_years, min_years, leave_own_year, transform):
    an = anomalies(raw, clim_years, min_years, leave_own_year)
    if transform is not None:
        an = transform(an)
    sub = sub.drop(columns=[c for c in SAT if c in sub.columns]).merge(an, on=["ID", "t"], how="left")
    return sub.dropna(subset=SAT)


# ---- splits (copied from beech-masting-spatial-proxy) ----

def blocks(sites, block_m=BLOCK_M):
    """Block id of each site: the block_m square of EPSG:6691 holding it. sites: ID, x, y_m."""
    bx = np.floor(sites.x.to_numpy() / block_m).astype(int)
    by = np.floor(sites.y_m.to_numpy() / block_m).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=sites.ID.to_numpy())


def spatial_folds(sites, repeat, block_m=BLOCK_M, buffer_m=BUFFER_M):
    """[(test_ids, train_ids)] for one repeat. Blocks are shuffled with seed `repeat` and dealt to the 5 folds in
    turn; training leaves out the test sites and every site within buffer_m of one."""
    b = blocks(sites, block_m)
    names = sorted(b.unique())
    rng = np.random.default_rng(repeat)
    order = rng.permutation(len(names))
    fold_of = {names[i]: k % FOLDS for k, i in enumerate(order)}
    xy = sites.set_index("ID")[["x", "y_m"]]
    out = []
    for f in range(FOLDS):
        test = [i for i in sites.ID if fold_of[b[i]] == f]
        if not test:
            continue
        d = np.hypot(xy.x.to_numpy()[:, None] - xy.loc[test, "x"].to_numpy()[None, :],
                     xy.y_m.to_numpy()[:, None] - xy.loc[test, "y_m"].to_numpy()[None, :]).min(axis=1)
        train = [i for i, dd in zip(xy.index, d) if dd > buffer_m and i not in set(test)]
        out.append((test, train))
    return out


def neighbour_lag(rows, ranks, train_ids, sites, k=K_NEAR):
    """For each row: mean rank at t - 1 over the k nearest sites in train_ids (not the row's own) that have a rank
    at t - 1. ranks: ID, year, rank (valid ranks only)."""
    xy = sites.set_index("ID")[["x", "y_m"]]
    train_ids = np.asarray(sorted(train_ids))
    have = {y: set(g.ID) for y, g in ranks.groupby("year")}
    val = ranks.set_index(["ID", "year"])["rank"]
    tx, ty = xy.loc[train_ids, "x"].to_numpy(), xy.loc[train_ids, "y_m"].to_numpy()
    order = {}
    out = np.full(len(rows), np.nan)
    for n, (i, t) in enumerate(zip(rows.ID.to_numpy(), rows.t.to_numpy())):
        if i not in order:
            d = np.hypot(tx - xy.at[i, "x"], ty - xy.at[i, "y_m"])
            order[i] = [j for j in train_ids[np.argsort(d, kind="stable")] if j != i]
        hv = have.get(t - 1, set())
        near = [j for j in order[i] if j in hv][:k]
        if near:
            out[n] = float(np.mean([val[(j, t - 1)] for j in near]))
    return out


# ---- schemes ----

def _predict(train, test, models, repeat):
    out = []
    for m in models:
        out.append(pd.DataFrame({"ID": test.ID.to_numpy(), "t": test.t.to_numpy(), "y": test.y.to_numpy(),
                                 "model": m, "pred": fit_predict(train, test, m), "repeat": repeat}))
    return out


def run_A(rows, raw, test_years, train_years, models, min_years, transform=None):
    """Leave one year out with the site's own lag. Returns long table: ID, t, y, model, pred, repeat (0)."""
    rows = rows[rows.lag_own.notna()].assign(lag=lambda d: d.lag_own)
    out = []
    for t in test_years:
        clim = [y for y in train_years if y not in (t, t + 1)]
        sub = with_anomalies(rows, raw, clim, min_years, False, transform)
        test = sub[sub.t == t]
        train = sub[sub.t.isin(clim)]
        if test.empty:
            continue
        out += _predict(train, test, models, 0)
    return pd.concat(out, ignore_index=True)


def run_BC(rows, raw, ranks, sites, scheme, test_years, train_years, models, min_years, repeats=REPEATS, k=K_NEAR,
           block_m=BLOCK_M, buffer_m=BUFFER_M, transform=None, lag_cache=None):
    """Spatial blocks (B) or spatial blocks x leave one year out (C). transform(anomaly table) may replace the
    anomalies (the permutation checks). lag_cache (a dict) keeps the neighbour lag of each fold between calls."""
    out = []
    an_cache = {}
    for r in range(repeats):
        for f, (test_ids, train_ids) in enumerate(spatial_folds(sites, r, block_m, buffer_m)):
            key = (r, f, k, block_m, buffer_m)
            if lag_cache is not None and key in lag_cache:
                sub = lag_cache[key]
            else:
                sub = rows[rows.ID.isin(set(test_ids) | set(train_ids))].copy()
                sub["lag"] = neighbour_lag(sub, ranks, train_ids, sites, k)
                sub = sub[sub.lag.notna()]
                if lag_cache is not None:
                    lag_cache[key] = sub
            if scheme == "B":
                groups = [(None, list(train_years), True)]
            else:
                groups = [(t, [y for y in train_years if y not in (t, t + 1)], False) for t in test_years]
            for t, clim, own in groups:
                ck = (tuple(clim), own)
                if ck not in an_cache:
                    an_cache[ck] = with_anomalies(rows[["ID", "t"]], raw, clim, min_years, own, transform)
                s2 = sub.merge(an_cache[ck], on=["ID", "t"], how="inner")
                test = s2[s2.ID.isin(test_ids) & (s2.t.isin(test_years) if t is None else (s2.t == t))]
                train = s2[s2.ID.isin(train_ids) & s2.t.isin(clim)]
                if test.empty:
                    continue
                out += _predict(train, test, models, r)
    return pd.concat(out, ignore_index=True)


# ---- scores ----

def spearman(a, b):
    a, b = pd.Series(np.asarray(a, float)), pd.Series(np.asarray(b, float))
    if a.nunique() < 2 or b.nunique() < 2:
        return 0.0
    return float(a.rank().corr(b.rank()))


def within_year(p):
    """p: ID, t, y, pred (one row per site and year). Spearman across sites within each year with at least
    MIN_ROWS_PER_YEAR rows (0 if predictions or observations are constant), and the equal-weight mean."""
    by, dropped = {}, []
    for t, g in p.groupby("t"):
        if len(g) < MIN_ROWS_PER_YEAR:
            dropped.append(int(t))
            continue
        by[int(t)] = spearman(g.pred, g.y)
    return {"by_year": by, "mean": float(np.mean(list(by.values()))) if by else math.nan,
            "years_dropped": dropped, "rows": int(sum(len(g) for t, g in p.groupby("t") if int(t) in by))}


def centered_rmse(p):
    """RMSE after removing each year's mean from predictions and observations (a diagnostic, not a forecast)."""
    c = p.assign(pc=p.pred - p.groupby("t").pred.transform("mean"), yc=p.y - p.groupby("t").y.transform("mean"))
    return float(math.sqrt(((c.pc - c.yc) ** 2).mean()))


def row_means(pred):
    """Per model and row: the prediction averaged over repeats."""
    return pred.groupby(["model", "ID", "t"]).agg(y=("y", "first"), pred=("pred", "mean"),
                                                  n=("pred", "size")).reset_index()


def common_rows(p, models):
    keys = None
    for m in models:
        k = set(map(tuple, p.loc[p.model == m, ["ID", "t"]].to_numpy()))
        keys = k if keys is None else keys & k
    idx = list(map(tuple, p[["ID", "t"]].to_numpy()))
    return p[[k in keys for k in idx]].reset_index(drop=True)


def evaluate(pred, models):
    """Scores of each model on the rows all models have."""
    p = common_rows(row_means(pred[pred.model.isin(models)]), models)
    scores, within = {}, {}
    for m in models:
        g = p[p.model == m]
        err = g.pred - g.y
        within[m] = within_year(g)
        scores[m] = {"n": int(len(g)), "years": int(g.t.nunique()), "rmse": float(math.sqrt((err ** 2).mean())),
                     "mae": float(err.abs().mean()), "spearman_pooled": spearman(g.pred, g.y),
                     "centered_rmse": centered_rmse(g), "within_year_spearman": within[m]["mean"]}
    return {"scores": scores, "within": within, "rows": p}


def diff_bootstrap(a, b, reps=2000, seed=0):
    """Mean over years of a[t] - b[t] (within-year Spearman by year) and its 90% interval from resampling years."""
    years = sorted(set(a) & set(b))
    d = np.array([a[t] - b[t] for t in years])
    rng = np.random.default_rng(seed)
    boot = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(reps)])
    lo, hi = np.percentile(boot, [5, 95])
    return {"years": len(years), "diff": float(d.mean()), "lo90": float(lo), "hi90": float(hi)}


def rule(boot):
    """The plan's rule: supported if the point estimate > 0 and the 90% lower bound > 0."""
    return "supported" if boot["diff"] > 0 and boot["lo90"] > 0 else "not supported"

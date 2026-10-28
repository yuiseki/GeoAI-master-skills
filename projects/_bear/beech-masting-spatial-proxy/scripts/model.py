"""Models, splits and scores of EXPERIMENT_PLAN.md (site x target year t, rank 0-3).

Rows carry: ID, t, y (rank at t), lag_own (rank at t - 1, NaN if missing), x and y_m (EPSG:6691 metres),
dT, Tsp, Ts1, Ts2, P, PET, WB and the terrain columns. The schemes:

    A  unknown year: leave one target year out; training drops years t and t + 1 (t + 1 carries t as its lag)
    B  unknown site: 50 km blocks in EPSG:6691 -> 5 folds at random (repeat r uses seed r), sites within 15 km of a
       test site are left out of training; every year is on both sides
    C  unknown site and year: fold f x year t; training = sites outside f and its buffer, years other than t, t + 1

In B and C the lag of every row (training and test) is the mean rank at t - 1 of the 5 nearest training sites other
than the row's own site that have a rank at t - 1; in A it is the site's own rank at t - 1. M0 is the site's mean
rank over the training rows (A) or the mean of that over the 5 nearest training sites (B, C). All other models are
least squares with an intercept, predictions clipped to 0-3.
"""

import math

import numpy as np
import pandas as pd

K_NEAR = 5
BLOCK_M = 50_000.0
BUFFER_M = 15_000.0
FOLDS = 5
REPEATS = 10
TERRAIN = ["elev", "slope", "northness", "eastness", "relief", "tpi"]


def features(model, water="w1"):
    """Columns of a model (before the intercept). Interactions are built in design()."""
    m1 = ["lag"]
    m2 = m1 + ["dT"]
    m3 = m2 + TERRAIN
    m4 = m3 + (["WB"] if water == "w1" else ["P", "PET"])
    m5 = m4 + ["dT:elev", "WB:elev", "WB:northness"]
    table = {"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5, "M7": m1 + ["Ts1", "Ts2", "Tsp"]}
    return table[model]


def design(rows, cols, elev_centre):
    """Matrix with an intercept. elev in the interactions is (elev - elev_centre) / 1000 (km from the training mean)."""
    out = [np.ones(len(rows))]
    for c in cols:
        if ":" in c:
            a, b = c.split(":")
            va = rows[a].to_numpy(float)
            vb = (rows[b].to_numpy(float) - elev_centre) / 1000.0 if b == "elev" else rows[b].to_numpy(float)
            out.append(va * vb)
        else:
            out.append(rows[c].to_numpy(float))
    return np.column_stack(out)


def fit_predict(train, test, model, water="w1", year_effect=False):
    """Least squares on train, predictions for test clipped to 0-3. year_effect adds one intercept per training year
    (only for B, where every test year is also a training year)."""
    cols = features(model, water)
    centre = float(train["elev"].mean())
    Xtr, Xte = design(train, cols, centre), design(test, cols, centre)
    if year_effect:
        years = sorted(train.t.unique())
        if not set(test.t).issubset(years):
            raise ValueError("year effects need every test year in training")
        Xtr = np.column_stack([Xtr[:, 1:]] + [(train.t.to_numpy() == y).astype(float) for y in years])
        Xte = np.column_stack([Xte[:, 1:]] + [(test.t.to_numpy() == y).astype(float) for y in years])
    beta, *_ = np.linalg.lstsq(Xtr, train.y.to_numpy(float), rcond=None)
    return np.clip(Xte @ beta, 0.0, 3.0)


# ---- splits ----

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


# ---- neighbour features ----

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


def neighbour_mean(test_ids, train_rows, sites, k=K_NEAR):
    """M0 for unseen sites: per test site, the mean over its k nearest training sites of their mean rank."""
    xy = sites.set_index("ID")[["x", "y_m"]]
    means = train_rows.groupby("ID").y.mean()
    ids = means.index.to_numpy()
    out = {}
    for i in test_ids:
        d = np.hypot(xy.loc[ids, "x"].to_numpy() - xy.at[i, "x"], xy.loc[ids, "y_m"].to_numpy() - xy.at[i, "y_m"])
        near = [j for j in ids[np.argsort(d, kind="stable")] if j != i][:k]
        out[i] = float(means.loc[near].mean())
    return out


# ---- schemes ----

def run_A(rows, test_years, train_years, models, water):
    """Leave one year out with the site's own lag. Returns long table: ID, t, y, model, pred, repeat (0)."""
    rows = rows[rows.lag_own.notna()].assign(lag=lambda d: d.lag_own)
    out = []
    for t in test_years:
        test = rows[rows.t == t]
        train = rows[rows.t.isin(train_years) & ~rows.t.isin([t, t + 1])]
        if test.empty:
            continue
        site_mean = train.groupby("ID").y.mean()
        for m in models:
            p = test.ID.map(site_mean).to_numpy() if m == "M0" else fit_predict(train, test, m, water)
            out.append(pd.DataFrame({"ID": test.ID, "t": t, "y": test.y, "model": m, "pred": p, "repeat": 0}))
    return pd.concat(out, ignore_index=True)


def run_BC(rows, ranks, sites, scheme, test_years, train_years, models, water, repeats=REPEATS, k=K_NEAR,
           block_m=BLOCK_M, buffer_m=BUFFER_M, transform=None, lag_cache=None):
    """Spatial blocks (B) or spatial blocks x leave one year out (C). transform(rows) may replace feature columns
    (used by the permutation checks) after the lag is built. lag_cache (a dict) keeps the neighbour lag of each
    fold between calls with the same rows, ranks and settings."""
    out = []
    for r in range(repeats):
        for f, (test_ids, train_ids) in enumerate(spatial_folds(sites, r, block_m, buffer_m)):
            key = (r, f, k, block_m, buffer_m)
            if lag_cache is not None and key in lag_cache:
                sub = lag_cache[key].copy()
            else:
                sub = rows[rows.ID.isin(set(test_ids) | set(train_ids))].copy()
                sub["lag"] = neighbour_lag(sub, ranks, train_ids, sites, k)
                sub = sub[sub.lag.notna()]
                if lag_cache is not None:
                    lag_cache[key] = sub.copy()
            if transform is not None:
                sub = transform(sub)
            tr_all = sub[sub.ID.isin(train_ids) & sub.t.isin(train_years)]
            te_all = sub[sub.ID.isin(test_ids) & sub.t.isin(test_years)]
            groups = [(None, te_all, tr_all)] if scheme == "B" else [
                (t, te_all[te_all.t == t], tr_all[~tr_all.t.isin([t, t + 1])]) for t in test_years]
            for _, test, train in groups:
                if test.empty:
                    continue
                m0 = neighbour_mean(sorted(set(test.ID)), train, sites, k)
                for m in models:
                    if m == "M0":
                        p = test.ID.map(m0).to_numpy()
                    elif m == "M1y":
                        p = fit_predict(train, test, "M1", water, year_effect=True)
                    else:
                        p = fit_predict(train, test, m, water)
                    out.append(pd.DataFrame({"ID": test.ID, "t": test.t, "y": test.y, "model": m, "pred": p,
                                             "repeat": r}))
    return pd.concat(out, ignore_index=True)


# ---- scores ----

def row_errors(pred):
    """Per row and model: squared error averaged over repeats, mean prediction. Index (ID, t)."""
    p = pred.assign(se=(pred.pred - pred.y) ** 2, ae=(pred.pred - pred.y).abs())
    return p.groupby(["model", "ID", "t"]).agg(y=("y", "first"), se=("se", "mean"), ae=("ae", "mean"),
                                                pred=("pred", "mean"), n=("pred", "size")).reset_index()


def common_rows(err, models):
    keys = None
    for m in models:
        k = set(map(tuple, err.loc[err.model == m, ["ID", "t"]].to_numpy()))
        keys = k if keys is None else keys & k
    idx = err.set_index(["ID", "t"]).index
    return err[[k in keys for k in idx]]


def scores(err):
    """RMSE, MAE and Spearman per model (rows already common)."""
    out = {}
    for m, g in err.groupby("model"):
        out[m] = {"n": len(g), "years": int(g.t.nunique()), "rmse": float(math.sqrt(g.se.mean())),
                  "mae": float(g.ae.mean()), "spearman": float(g.pred.rank().corr(g.y.rank()))}
    return out


def year_bootstrap(err, cand, comp, reps=2000, seed=0):
    """RMSE(cand) - RMSE(comp) on the same rows, and its 90% interval from resampling test years (all rows of a
    year move together)."""
    a = err[err.model == cand].set_index(["ID", "t"]).se
    b = err[err.model == comp].set_index(["ID", "t"]).se
    j = pd.DataFrame({"a": a, "b": b}).dropna().reset_index()
    years = np.array(sorted(j.t.unique()))
    sa = j.groupby("t").a.agg(["sum", "size"]).reindex(years)
    sb = j.groupby("t").b.sum().reindex(years)
    point = math.sqrt(j.a.mean()) - math.sqrt(j.b.mean())
    rng = np.random.default_rng(seed)
    d = np.empty(reps)
    for i in range(reps):
        pick = rng.integers(0, len(years), len(years))
        n = sa["size"].to_numpy()[pick].sum()
        d[i] = math.sqrt(sa["sum"].to_numpy()[pick].sum() / n) - math.sqrt(sb.to_numpy()[pick].sum() / n)
    lo, hi = np.percentile(d, [5, 95])
    return {"cand": cand, "comp": comp, "rows": len(j), "years": len(years), "diff": point, "lo90": float(lo),
            "hi90": float(hi)}


def repeat_diffs(pred, cand, comp):
    """RMSE(cand) - RMSE(comp) within each repeat, on the rows both have in that repeat."""
    out = []
    for r, g in pred.groupby("repeat"):
        a = g[g.model == cand].set_index(["ID", "t"]).pred
        b = g[g.model == comp].set_index(["ID", "t"]).pred
        y = g[g.model == cand].set_index(["ID", "t"]).y
        j = pd.DataFrame({"a": a, "b": b, "y": y}).dropna()
        out.append(math.sqrt(((j.a - j.y) ** 2).mean()) - math.sqrt(((j.b - j.y) ** 2).mean()))
    return out


def rule(boot):
    """The plan's rule: supported if the 90% upper bound < 0, rejected if the point estimate >= 0, else undecided."""
    if boot["hi90"] < 0:
        return "supported"
    if boot["diff"] >= 0:
        return "rejected"
    return "undecided"

"""Rolling-origin evaluation of weekly bear-report forecasts per municipality.

For each origin o (a week index) and horizon h, every model gets only the weeks 0..o and forecasts
week o+h for every municipality. The origins run from --origin-from to the last one that still has
a target at the longest horizon, the same for every model and horizon. Nothing after o reaches a
model: the series is cut at o before any feature is built.

Baselines
    naive            the last week's count
    mean_short       the mean of the last 4 weeks (3 months in the monthly config)
    muni_mean        the municipality's mean over all weeks so far
    seasonal_naive   the count one year (52 weeks) before the target week
    seasonal3        the mean of the 3 weeks around that week one year before
    recent_year      the mean of the last 52 weeks (12 months): recent level, no season
    seasonal_3y      the mean of the same week in each of the last three years that exist
Models (fitted at every origin on the pairs (t, t+h) with t+h <= o)
    glm              Poisson regression on log-count features (lags, windows, state totals, season, level)
    hgb              histogram gradient boosting with a Poisson loss; adds last year's counts
    glm_nb, hgb_nb   the same with the neighbouring municipalities' recent counts (needs --adjacency)
    hier_hgb         boosting on the state total, then spread over municipalities by their recent share

Scores are over all origins x municipalities: MAE, RMSE, mean Poisson deviance, bias (forecast
minus actual), and, per origin, how much of the week's reports fall in the k municipalities the
forecast ranks highest ("capture", against the same share for the best possible k).

Usage:
    uvx --with numpy --with pandas --with scikit-learn --with pyarrow --with scipy python evaluate.py \
        TABLE.parquet OUT_PREFIX [--horizons 1 2 4] [--origin-from 52] [--models glm hgb] [--workers 8] \
        [--period weekly|monthly]
"""

import argparse
import json
import os

import numpy as np

FEATURES = ["l0", "l1", "m4", "m12", "S0", "S4", "level", "yoy", "ly", "lyS", "sin1", "cos1", "sin2", "cos2", "logpop", "nb0", "nb4"]
GLM_FEATURES = ["l0", "m4", "m12", "S4", "level", "sin1", "cos1", "sin2", "cos2", "logpop"]
NEIGHBOUR_FEATURES = ["nb0", "nb4"]
BASELINES = ["naive", "mean_short", "muni_mean", "seasonal_naive", "seasonal3", "seasonal_3y", "recent_year"]

# period of the season, the short and long windows, and the calendar unit of one step
WEEKLY = {"season": 52, "w_short": 4, "w_long": 12, "unit": "W"}
MONTHLY = {"season": 12, "w_short": 3, "w_long": 12, "unit": "M"}


def window_mean(Y, w):
    """Mean of the last w columns up to and including each column t (a shorter window at the start)."""
    C = np.concatenate([np.zeros((Y.shape[0], 1)), np.cumsum(Y, axis=1)], axis=1)
    t = np.arange(Y.shape[1])
    lo = np.maximum(0, t + 1 - w)
    return (C[:, t + 1] - C[:, lo]) / (t + 1 - lo)


def adjacency_matrix(pairs, codes):
    """Row-normalised neighbour weights from pairs of municipality codes (each pair counts both ways).

    A municipality with no neighbour keeps a zero row. A code that is not in `codes` stops the run.
    """
    idx = {c: i for i, c in enumerate(codes)}
    W = np.zeros((len(codes), len(codes)))
    for a, b in pairs:
        if a not in idx or b not in idx:
            raise ValueError(f"unknown municipality code in the pair ({a}, {b})")
        if a != b:
            W[idx[a], idx[b]] = 1.0
            W[idx[b], idx[a]] = 1.0
    rows = W.sum(axis=1, keepdims=True)
    return np.divide(W, rows, out=np.zeros_like(W), where=rows > 0)


def allocate(total, Y_o, recent):
    """Spread a forecast total over municipalities by their share of the last `recent` periods of Y_o.

    When those periods are all zero, the long-run share is used; when that is zero too, an even share.
    """
    r = Y_o[:, -recent:].sum(axis=1)
    if r.sum() <= 0:
        r = Y_o.sum(axis=1)
    if r.sum() <= 0:
        r = np.ones(Y_o.shape[0])
    return total * r / r.sum()


def features(Y, dates, pop, h, cfg=WEEKLY, W=None):
    """Feature tensor F[muni, t, feature] for target week t+h, from Y[:, :t+1] only.

    `dates` are the Mondays of the weeks (or the months, for the monthly config). The calendar of the
    target period is known in advance; counts are not. Features that need a year of history are NaN
    before it exists.
    """
    m, T = Y.shape
    L = np.log1p(Y)
    S = Y.mean(axis=0, keepdims=True)  # state mean per municipality, per week
    F = np.full((m, T, len(FEATURES)), np.nan)
    col = {n: i for i, n in enumerate(FEATURES)}
    F[:, :, col["l0"]] = L
    F[:, 1:, col["l1"]] = L[:, :-1]
    F[:, 0, col["l1"]] = L[:, 0]
    F[:, :, col["m4"]] = np.log1p(window_mean(Y, cfg["w_short"]))
    F[:, :, col["m12"]] = np.log1p(window_mean(Y, cfg["w_long"]))
    F[:, :, col["S0"]] = np.log1p(S)
    S4 = window_mean(S, cfg["w_short"])
    F[:, :, col["S4"]] = np.log1p(S4)
    F[:, :, col["level"]] = np.log1p(window_mean(Y, T))  # expanding mean up to t
    k = cfg["season"]
    if T > k:
        F[:, k:, col["yoy"]] = np.log1p(S4[:, k:]) - np.log1p(S4[:, :-k])
    ly = np.full((m, T), np.nan)
    lyS = np.full((m, T), np.nan)
    for t in range(T):
        s = t + h - k
        if 0 <= s <= t:
            ly[:, t] = L[:, s]
            lyS[:, t] = np.log1p(S[0, s])
    F[:, :, col["ly"]] = ly
    F[:, :, col["lyS"]] = lyS
    if cfg["unit"] == "W":
        target = dates + np.timedelta64(7 * h, "D")
        doy = (target - target.astype("datetime64[Y]")).astype("timedelta64[D]").astype(float) + 3.0
        ph = 2 * np.pi * doy / 365.25
    else:  # one value per month: the phase is the middle of the target month
        target = dates.astype("datetime64[M]") + np.timedelta64(h, "M")
        month = (target - target.astype("datetime64[Y]").astype("datetime64[M]")).astype(int) + 1
        ph = 2 * np.pi * (month - 0.5) / 12
    F[:, :, col["sin1"]] = np.sin(ph)
    F[:, :, col["cos1"]] = np.cos(ph)
    F[:, :, col["sin2"]] = np.sin(2 * ph)
    F[:, :, col["cos2"]] = np.cos(2 * ph)
    F[:, :, col["logpop"]] = np.log(pop)[:, None]
    if W is not None:  # the neighbours' counts up to t: the mean over the neighbours (row-normalised W)
        F[:, :, col["nb0"]] = np.log1p(W @ Y)
        F[:, :, col["nb4"]] = np.log1p(W @ window_mean(Y, cfg["w_short"]))
    return F, FEATURES


def training_pairs(Y, dates, pop, o, h, cfg=WEEKLY, W=None):
    """(X, y, w): features at week t and the count at t+h for every municipality, t+h <= o."""
    Yo = Y[:, : o + 1]
    F, names = features(Yo, dates[: o + 1], pop, h, cfg, W)
    m = Y.shape[0]
    ts = np.arange(0, o - h + 1)
    X = F[:, ts, :].reshape(m * len(ts), len(names))
    y = Yo[:, ts + h].reshape(-1)
    w = np.tile(ts, m)
    return X, y, w


def baseline(Y, o, h, name, cfg=WEEKLY):
    Yo = Y[:, : o + 1]
    if name == "naive":
        return Yo[:, o].copy()
    if name == "mean_short":
        return Yo[:, max(0, o - cfg["w_short"] + 1) : o + 1].mean(axis=1)
    if name == "muni_mean":
        return Yo.mean(axis=1)
    if name == "recent_year":  # the mean of the last whole season of periods: recent, with no season in it
        return Yo[:, max(0, o - cfg["season"] + 1) : o + 1].mean(axis=1)
    if name == "seasonal_3y":  # the same period in each of the last three years, those that exist
        idx = [o + h - k * cfg["season"] for k in (1, 2, 3)]
        idx = [i for i in idx if 0 <= i <= o]
        return Yo[:, idx].mean(axis=1) if idx else np.full(Y.shape[0], np.nan)
    s = o + h - cfg["season"]
    if s < 0:
        return np.full(Y.shape[0], np.nan)
    if name == "seasonal_naive":
        return Yo[:, s].copy()
    if name == "seasonal3":
        return Yo[:, max(0, s - 1) : s + 2].mean(axis=1)
    raise ValueError(name)


def usable_columns(X, names):
    """Indices of the columns with at least two distinct non-NaN values, and the names of those left out."""
    keep, dropped = [], []
    for j, n in enumerate(names):
        v = X[:, j]
        if len(np.unique(v[~np.isnan(v)])) >= 2:
            keep.append(j)
        else:
            dropped.append(n)
    return keep, dropped


def model_forecast(name, Y, dates, pop, o, h, cfg=WEEKLY, W=None):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import PoissonRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if name.endswith("_nb") and W is None:
        raise ValueError(f"{name} needs the neighbour weights W")
    if name == "hier_hgb":
        # forecast the state total, then spread it over the municipalities by their recent share
        Ys = Y[:, : o + 1].sum(axis=0, keepdims=True)
        ps = np.array([pop.sum()])
        Xs, ys, _ = training_pairs(Ys, dates, ps, o, h, cfg)
        Fs, names = features(Ys, dates[: o + 1], ps, h, cfg)
        keep, _ = usable_columns(Xs, names)
        mdl = HistGradientBoostingRegressor(
            loss="poisson", max_iter=150, learning_rate=0.05, max_depth=3, min_samples_leaf=10,
            l2_regularization=1.0, random_state=0,
        )
        mdl.fit(Xs[:, keep], ys)
        total = float(np.clip(mdl.predict(Fs[:, o, :][:, keep])[0], 0, None))
        return allocate(total, Y[:, : o + 1], cfg["w_short"])
    base = name[:-3] if name.endswith("_nb") else name
    X, y, _ = training_pairs(Y, dates, pop, o, h, cfg, W if name.endswith("_nb") else None)
    Fo, names = features(Y[:, : o + 1], dates[: o + 1], pop, h, cfg, W if name.endswith("_nb") else None)
    Xo = Fo[:, o, :]
    if base == "glm":
        cols = [names.index(c) for c in GLM_FEATURES + (NEIGHBOUR_FEATURES if name.endswith("_nb") else [])]
        mdl = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1e-2, max_iter=2000))
        mdl.fit(X[:, cols], y)
        return np.clip(mdl.predict(Xo[:, cols]), 0, None)
    if base == "hgb":
        mdl = HistGradientBoostingRegressor(
            loss="poisson", max_iter=150, learning_rate=0.05, max_depth=4, min_samples_leaf=40,
            l2_regularization=1.0, random_state=0,
        )
        keep, _ = usable_columns(X, names)  # a column with one value (all NaN at the first origins) cannot be binned
        mdl.fit(X[:, keep], y)
        return np.clip(mdl.predict(Xo[:, keep]), 0, None)
    raise ValueError(name)


def poisson_deviance(y, mu):
    mu = np.clip(mu, 1e-3, None)
    term = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(np.mean(2 * (term - (y - mu))))


def capture(pred, actual, level, k=5):
    """Share of the actual reports that fall in the k municipalities with the highest forecast.

    Ties in the forecast are broken by the municipality's long-run level, the same for every model.
    """
    total = actual.sum()
    if total <= 0:
        return float("nan")
    order = np.lexsort((-level, -pred))
    return float(actual[order[:k]].sum() / total)


def block_bootstrap_interval(values, blocks, B=2000, seed=0, level=0.90):
    """Percentile interval of the mean of `values`, resampling whole blocks (e.g. calendar years) with replacement."""
    values = np.asarray(values, dtype=float)
    blocks = np.asarray(blocks)
    ids = np.unique(blocks)
    sums = np.array([values[blocks == b].sum() for b in ids])
    ns = np.array([(blocks == b).sum() for b in ids])
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(B, len(ids)))
    means = sums[draws].sum(axis=1) / ns[draws].sum(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def load_wide(table, target, period, time_col=None):
    """(codes, Y[muni, t], dates[t], pop[muni]) from a municipality x period Parquet, sorted by code and time."""
    import pandas as pd

    tcol = time_col or ("week_start" if period == "weekly" else "month_start")
    df = pd.read_parquet(table).sort_values(["code5", tcol])
    codes = sorted(df.code5.unique())
    wide = df.pivot(index="code5", columns=tcol, values=target).loc[codes]
    Y = wide.to_numpy(dtype=float)
    dates = wide.columns.to_numpy().astype("datetime64[D]" if period == "weekly" else "datetime64[M]")
    pop = df.drop_duplicates("code5").set_index("code5").loc[codes, "population"].to_numpy(dtype=float)
    return codes, Y, dates, pop


def _one(args):
    Y, dates, pop, o, h, names, cfg, W = args
    out = {}
    for n in names:
        out[n] = baseline(Y, o, h, n, cfg) if n in BASELINES else model_forecast(n, Y, dates, pop, o, h, cfg, W)
    return o, h, out


def summarise(rows, k=5):
    """rows: list of dict(o, h, week, model, pred[m], actual[m], level[m]) -> dict of scores per (model, h)."""
    import collections

    acc = collections.defaultdict(lambda: {"y": [], "p": [], "cap": [], "orc": [], "tot_p": [], "tot_y": []})
    for r in rows:
        a = acc[(r["model"], r["h"])]
        a["y"].append(r["actual"])
        a["p"].append(r["pred"])
        a["cap"].append(capture(r["pred"], r["actual"], r["level"], k))
        a["orc"].append(capture(r["actual"], r["actual"], r["level"], k))
        a["tot_p"].append(r["pred"].sum())
        a["tot_y"].append(r["actual"].sum())
    res = {}
    for (model, h), a in acc.items():
        y = np.concatenate(a["y"])
        p = np.concatenate(a["p"])
        cap = np.array(a["cap"])
        orc = np.array(a["orc"])
        ok = ~np.isnan(cap)
        tp, ty = np.array(a["tot_p"]), np.array(a["tot_y"])
        res[(model, h)] = {
            "n": int(len(y)),
            "mae": float(np.mean(np.abs(p - y))),
            "rmse": float(np.sqrt(np.mean((p - y) ** 2))),
            "dev": poisson_deviance(y, p),
            "bias": float(np.mean(p - y)),
            "mae_log1p": float(np.mean(np.abs(np.log1p(p) - np.log1p(y)))),
            "state_mae": float(np.mean(np.abs(tp - ty))),
            "capture": float(cap[ok].mean()),
            "oracle": float(orc[ok].mean()),
            "n_origins_with_reports": int(ok.sum()),
        }
    return res


def main():
    from concurrent.futures import ProcessPoolExecutor

    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("out_prefix")
    ap.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 4])
    ap.add_argument("--origin-from", type=int, default=52)
    ap.add_argument("--models", nargs="+", default=BASELINES + ["glm", "hgb"])
    ap.add_argument("--target", default="bear")
    ap.add_argument("--adjacency", default=None, help="Parquet of neighbour pairs (code5_a, code5_b); needed by *_nb models")
    ap.add_argument("--period", choices=["weekly", "monthly"], default="weekly")
    ap.add_argument("--time-col", default=None, help="week_start or month_start (default by --period)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    cfg = WEEKLY if a.period == "weekly" else MONTHLY
    codes, Y, dates, pop = load_wide(a.table, a.target, a.period, a.time_col)
    m, T = Y.shape
    hmax = max(a.horizons)
    origins = list(range(a.origin_from, T - hmax))
    print(f"{m} municipalities x {T} {a.period} periods; origins {origins[0]}..{origins[-1]} ({len(origins)}), horizons {a.horizons}, models {a.models}")
    print(f"origin weeks {dates[origins[0]]} .. {dates[origins[-1]]}; targets up to {dates[origins[-1] + hmax]}")

    W = None
    if a.adjacency:
        pairs = pd.read_parquet(a.adjacency)[["code5_a", "code5_b"]].itertuples(index=False, name=None)
        W = adjacency_matrix(pairs, codes)
        print(f"neighbour weights: {int((W > 0).sum())} directed links, {int((W.sum(axis=1) == 0).sum())} municipalities without a neighbour")
    jobs = [(Y, dates, pop, o, h, a.models, cfg, W) for o in origins for h in a.horizons]
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for o, h, out in ex.map(_one, jobs, chunksize=4):
            actual = Y[:, o + h]
            level = np.log1p(Y[:, : o + 1].mean(axis=1))
            for n, p in out.items():
                rows.append({"o": o, "h": h, "week": str(dates[o + h]), "model": n, "pred": p, "actual": actual, "level": level})

    # predictions in long form, for later checks
    recs = []
    for r in rows:
        for i, c in enumerate(codes):
            recs.append((r["model"], r["h"], r["o"], str(dates[r["o"]]), r["week"], c, float(r["actual"][i]), float(r["pred"][i])))
    pd.DataFrame(recs, columns=["model", "h", "origin", "origin_week", "target_week", "code5", "actual", "pred"]).to_parquet(a.out_prefix + "_predictions.parquet")

    res = summarise(rows)
    out = {f"{m_}|h{h}": v for (m_, h), v in res.items()}
    json.dump(out, open(a.out_prefix + "_scores.json", "w"), indent=1, ensure_ascii=False)
    print(f"{'model':16s} {'h':>2s} {'n':>6s} {'MAE':>7s} {'RMSE':>7s} {'dev':>7s} {'bias':>7s} {'logMAE':>7s} {'stMAE':>7s} {'cap5':>6s} {'oracle':>6s}")
    for (m_, h), v in sorted(res.items(), key=lambda kv: (kv[0][1], kv[1]["dev"] if np.isfinite(kv[1]["dev"]) else 1e9)):
        print(f"{m_:16s} {h:2d} {v['n']:6d} {v['mae']:7.3f} {v['rmse']:7.2f} {v['dev']:7.3f} {v['bias']:7.3f} {v['mae_log1p']:7.3f} {v['state_mae']:7.1f} {v['capture']:6.3f} {v['oracle']:6.3f}")


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()

"""The candidate models of the plan (B1): least squares with one intercept per prefecture and the cues as they are.

The design table has one row per prefecture and target year t: the fruiting index F(t), F(t-1), Ts(t-1), Ts(t-2),
dT = Ts(t-1) - Ts(t-2), Tsp(t), and Ts(t+1) for the placebo of B3.
"""

import numpy as np
import pandas as pd

CANDIDATES = {
    "M0": [],
    "M1": ["F_lag"],
    "M2": ["Ts_lag1"],
    "M3": ["dT"],
    "M4": ["Ts_lag1", "Ts_lag2"],
    "M5": ["Ts_lag1", "F_lag"],
    "M6": ["dT", "F_lag"],
    "M7": ["Ts_lag1", "Ts_lag2", "F_lag", "Tsp"],
}
WEATHER = ["M2", "M3", "M4", "M5", "M6", "M7"]
ALL_FEATURES = ["F_lag", "Ts_lag1", "Ts_lag2", "dT", "Tsp"]


def design(index, cues, stage="fruiting"):
    """index: year, pref, stage, index. cues: pref, year, Ts, Tsp. One row per prefecture and target year."""
    f = index[index.stage == stage].pivot_table(index=["pref", "year"], values="index").reset_index()
    f = f.rename(columns={"index": "F"})
    rows = cues[["pref", "year"]].drop_duplicates().merge(f, on=["pref", "year"], how="left")
    c = cues.set_index(["pref", "year"])
    lag = f.set_index(["pref", "year"])["F"]

    def at(series, pref, year):
        return series.get((pref, year), np.nan)

    for name, src, shift in (("F_lag", lag, -1), ("Ts_lag1", c["Ts"], -1), ("Ts_lag2", c["Ts"], -2),
                             ("Tsp", c["Tsp"], 0), ("Ts_lead1", c["Ts"], 1)):
        rows[name] = [at(src, p, y + shift) for p, y in zip(rows.pref, rows.year)]
    rows["dT"] = rows.Ts_lag1 - rows.Ts_lag2
    rows["dT_lead"] = rows.Ts_lead1 - rows.Ts_lag2
    return rows.sort_values(["year", "pref"]).reset_index(drop=True)


PLACEBO = {"Ts_lag1": "Ts_lead1", "dT": "dT_lead"}


def placebo(feats):
    """The same model with the summer before the target year replaced by the summer after it (B3, F1)."""
    out = [PLACEBO.get(f, f) for f in feats]
    if out == list(feats):
        raise ValueError("the model has no summer of t-1 to replace")
    return out


def matrix(df, feats, prefs):
    dummies = np.column_stack([(df.pref == p).to_numpy(float) for p in prefs])
    return np.column_stack([dummies] + [df[f].to_numpy(float) for f in feats])


def fit(df, feats):
    prefs = sorted(df.pref.unique())
    X = matrix(df, feats, prefs)
    beta, *_ = np.linalg.lstsq(X, df.F.to_numpy(float), rcond=None)
    return {"features": list(feats), "prefs": prefs, "coef": [float(b) for b in beta]}


def predict(model, df):
    if not set(df.pref) <= set(model["prefs"]):
        raise ValueError("a prefecture without an intercept")
    return matrix(df, model["features"], model["prefs"]) @ np.array(model["coef"])


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def loyo(df, feats):
    """Leave-one-year-out predictions: all prefectures of a year are held out together."""
    pred = np.full(len(df), np.nan)
    for y in sorted(df.year.unique()):
        test = (df.year == y).to_numpy()
        pred[test] = predict(fit(df[~test], feats), df[test])
    return pred


def complete_rows(df, models=CANDIDATES):
    need = sorted({f for fs in models.values() for f in fs})
    return df.dropna(subset=["F"] + need).reset_index(drop=True)


def choose(scores, tol=1e-3):
    """The weather candidate with the smallest score; a tie (within tol) goes to the one with fewer cues."""
    best = min(scores[m] for m in WEATHER)
    tied = [m for m in WEATHER if scores[m] - best < tol]
    return min(tied, key=lambda m: (len(CANDIDATES[m]), scores[m]))


def year_bootstrap(df, preds, B=2000, seed=0):
    """Resample years (all prefectures of a year together). preds: {name: predictions aligned with df}.
    Returns {name: rmse per resample}."""
    rng = np.random.default_rng(seed)
    years = np.array(sorted(df.year.unique()))
    idx = {y: np.flatnonzero(df.year.to_numpy() == y) for y in years}
    y = df.F.to_numpy(float)
    out = {k: np.empty(B) for k in preds}
    for b in range(B):
        rows = np.concatenate([idx[v] for v in rng.choice(years, len(years))])
        for k, p in preds.items():
            out[k][b] = rmse(y[rows], np.asarray(p)[rows])
    return out

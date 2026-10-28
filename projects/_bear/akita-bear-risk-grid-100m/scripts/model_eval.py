"""Fit the risk models on some bear years and score them on a later one, per 100 m cell.

Models and baselines (the score ranks the cells; ties: the second key, then at random with seed 0)
    B_pop     people within about 500 m (second key: within 2 km)
    B_hist    past reports within about 1 km, as the mean yearly share (second key: within 3 km)
    B_env     gradient boosting on the static features only
    M_full    gradient boosting on the static features and the history of reports
    M_logit   logistic regression on the same features as M_full (log1p of the counts and distances,
              median imputation with missing indicators, standardised)
    M_full_shufhist   M_full with the history columns shuffled across cells within each year (falsification)

Every model gets only the bear years in --train as labels, and history features built from the years before
each row's year (features.history_features). Writes OUT.json (scores) and OUT_scores.npz (score per cell).

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --with numpy --with scipy \
        --with scikit-learn --with pandas --with pyarrow python model_eval.py ART_DIR OUT --train 2023 --test 2024
"""

import argparse
import json
import time

import numpy as np

import features as ft
import metrics as mt

HGB = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=500, l2_regularization=1.0, early_stopping=False)
SECOND = {"B_pop": ("pop_500", "pop_2000"), "B_hist": ("h_all_r1000", "h_all_r3000")}
LOG_PREFIX = ("pop_", "bldg_", "h_", "d_")


def load(art, reports="reports_by_year.npz"):
    wc, dem, pop, osm = (np.load(f"{art}/{n}.npz") for n in ("worldcover", "dem", "worldpop", "osm"))
    static = ft.static_features(wc, dem, pop, osm)
    rep = np.load(f"{art}/{reports}")
    counts = {int(k[1:]): rep[k].astype(float) for k in rep.files}
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    return static, counts, muni


def design(static, counts, muni, year, history=True):
    inside = muni >= 0
    cols = dict(static)
    if history:
        cols.update(ft.history_features(counts, year))
    names = list(cols)
    X = np.column_stack([cols[n][inside] for n in names]).astype(np.float32)
    c = counts[year][inside]
    return X, names, c > 0, c


def _logit():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))


def _log_cols(X, names):
    X = X.copy()
    for j, n in enumerate(names):
        if n.startswith(LOG_PREFIX):
            X[:, j] = np.sign(X[:, j]) * np.log1p(np.abs(X[:, j]))
    return X


def run_models(static, counts, muni, train_years, test_year, models, seed=0):
    """Score per prefecture cell for the test year, for each model."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    out = {}
    need_hist = any(m in models for m in ("M_full", "M_logit", "M_full_shufhist", "B_hist"))
    te = {h: design(static, counts, muni, test_year, history=h) for h in ({True, False} if need_hist else {False})}
    for m in models:
        if m in SECOND:
            X, names, _, _ = te[True] if m == "B_hist" else te[False]
            a, b = SECOND[m]
            out[m] = X[:, names.index(a)].astype(float) + 0.0
            out[m + "__second"] = X[:, names.index(b)].astype(float)
            continue
        hist = m != "B_env"
        parts = [design(static, counts, muni, y, history=hist) for y in train_years]
        Xtr = np.vstack([p[0] for p in parts])
        ytr = np.concatenate([p[2] for p in parts])
        Xte, names = te[hist][0], te[hist][1]
        if m == "M_full_shufhist":
            rng = np.random.default_rng(seed)
            hcols = [j for j, n in enumerate(names) if n.startswith("h_")]
            Xte = Xte.copy()
            Xtr = Xtr.copy()
            start = 0
            for p in parts:  # shuffle within each training year, and within the test year
                n = p[0].shape[0]
                Xtr[start:start + n, hcols] = Xtr[start:start + n][rng.permutation(n)][:, hcols]
                start += n
            Xte[:, hcols] = Xte[rng.permutation(len(Xte))][:, hcols]
        if m == "M_logit":
            mdl = _logit()
            mdl.fit(_log_cols(Xtr, names), ytr)
            out[m] = mdl.predict_proba(_log_cols(Xte, names))[:, 1]
        else:
            mdl = HistGradientBoostingClassifier(**HGB, random_state=seed)
            mdl.fit(Xtr, ytr)
            out[m] = mdl.predict_proba(Xte)[:, 1]
    return out


def evaluate(scores, y, c, blocks, compare, B=1000, seed=0):
    from sklearn.metrics import average_precision_score, roc_auc_score

    res, orders = {}, {}
    for m, s in scores.items():
        if m.endswith("__second"):
            continue
        orders[m] = mt.rank_order(s, scores.get(m + "__second"))
        r = {f"capture@{int(k * 100)}%": mt.capture(orders[m], y, k) for k in (0.01, 0.05, 0.10)}
        r["capture@5%_reports"] = mt.capture(orders[m], c, 0.05)  # the share of the reports, not of the cells
        r["auc"] = float(roc_auc_score(y, s))
        r["ap"] = float(average_precision_score(y, s))
        if not m.startswith("B_pop") and not m.startswith("B_hist"):
            r["mean_pred"] = float(np.mean(s))
            r["brier"] = float(np.mean((s - y) ** 2))
        res[m] = r
    res["obs_rate"] = float(y.mean())
    res["n_pos_cells"] = int(y.sum())
    res["n_cells"] = int(len(y))
    diffs = {}
    for a, b in compare:
        if a in orders and b in orders:
            point = mt.capture(orders[a], y, 0.05) - mt.capture(orders[b], y, 0.05)
            lo, hi, _ = mt.bootstrap_diff(orders[a], orders[b], y, blocks, 0.05, B=B, seed=seed)
            diffs[f"{a} - {b}"] = {"diff": point, "lo90": lo, "hi90": hi}
    res["diff_capture@5%"] = diffs
    return res


def main():
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("art")
    ap.add_argument("out")
    ap.add_argument("--train", type=int, nargs="+", required=True)
    ap.add_argument("--test", type=int, required=True)
    ap.add_argument("--models", nargs="+", default=["B_pop", "B_hist", "B_env", "M_full", "M_logit"])
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reports", default="reports_by_year.npz", help="the report counts to use for labels and history")
    a = ap.parse_args()
    if max(a.train) >= a.test:
        raise SystemExit("training years must come before the test year")
    t0 = time.time()
    static, counts, muni = load(a.art, a.reports)
    cells = pd.read_parquet(f"{a.art}/cells.parquet", columns=["ix", "iy"])
    blocks = (cells.ix.to_numpy() // 100) * 10000 + cells.iy.to_numpy() // 100  # 10 km x 10 km
    scores = run_models(static, counts, muni, a.train, a.test, a.models, seed=a.seed)
    _, _, y, c = design(static, counts, muni, a.test, history=False)
    compare = [("M_full", "B_hist"), ("M_full", "B_pop"), ("M_full", "B_env"), ("M_full", "M_logit"), ("M_full_shufhist", "B_env")]
    res = evaluate(scores, y, c, blocks, compare, B=a.boot, seed=a.seed)
    res["setup"] = {"train": a.train, "test": a.test, "seed": a.seed, "boot": a.boot, "blocks": int(len(np.unique(blocks))),
                    "hgb": HGB, "seconds": round(time.time() - t0)}
    json.dump(res, open(a.out + ".json", "w"), indent=1)
    np.savez_compressed(a.out + "_scores.npz", **{k: v.astype(np.float32) for k, v in scores.items()})
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

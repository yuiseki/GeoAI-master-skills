"""Score simple models on a fold table, out of fold, so that a baseline and a model share folds.

The fold table is a Parquet file with one row per (repeat, fold, id, role); role is train or test.
Each tested row is predicted once per repeat by a model fitted without it; the repeat's predictions
are scored together. Rows no fold tests are left out of the score, and n says how many were scored.

Models (regression / classification):
    mean / prior   the training mean, or the training share of class 1
    median         the training median (regression)
    group_mean     the training mean of the row's group; the overall mean for an unseen group
    linear         linear / logistic regression on standardised features
    hgb            histogram gradient boosting
Scores: rmse, mae, r2 (regression); log_loss, brier, auc, accuracy (classification, 0/1 target).

Usage:
    uvx --with duckdb --with scikit-learn python score_folds.py TABLE ID TARGET FEATURE [...] \
        --task regression|classification --models mean linear --folds-file folds.parquet [--group COL]
    or, without a fold table:  --cv rows|group [--folds 5] [--repeats 1]  (group needs --group)

TABLE must have no missing value in the columns used, and the folds must be made from the same rows.
"""

import argparse

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, log_loss, mean_absolute_error,
                             r2_score, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def predict_fold(name, task, Xtr, ytr, Xte, gtr=None, gte=None, seed=0):
    """Predictions for the test rows (class 1 probability for classification)."""
    if name in ("mean", "prior"):
        return np.full(len(Xte), float(ytr.mean()))
    if name == "median":
        return np.full(len(Xte), float(np.median(ytr)))
    if name == "group_mean":
        overall = float(ytr.mean())
        means = {k: float(ytr[gtr == k].mean()) for k in np.unique(gtr)}
        return np.array([means.get(k, overall) for k in gte])
    if name == "linear":
        est = LinearRegression() if task == "regression" else LogisticRegression(max_iter=1000)
        model = make_pipeline(StandardScaler(), est)
    elif name == "hgb":
        model = (HistGradientBoostingRegressor(random_state=seed) if task == "regression"
                 else HistGradientBoostingClassifier(random_state=seed))
    else:
        raise SystemExit(f"unknown model {name}")
    model.fit(Xtr, ytr)
    return model.predict(Xte) if task == "regression" else model.predict_proba(Xte)[:, 1]


def score(y, pred, task):
    if task == "classification":
        p = np.clip(pred, 1e-15, 1 - 1e-15)
        return {"log_loss": log_loss(y, p, labels=[0, 1]), "brier": brier_score_loss(y, p),
                "auc": roc_auc_score(y, p) if len(np.unique(y)) == 2 else float("nan"),
                "accuracy": accuracy_score(y, p >= 0.5)}
    return {"rmse": float(np.sqrt(np.mean((y - pred) ** 2))), "mae": mean_absolute_error(y, pred),
            "r2": r2_score(y, pred)}


def load_folds(path, ids):
    """{repeat: [(train indices, test indices), ...]}; every id must be a row of the data."""
    index = {v: i for i, v in enumerate(ids.tolist())}
    rows = duckdb.sql(f"select repeat, fold, id, role from '{path}' order by all").fetchall()
    missing = {r[2] for r in rows if r[2] not in index}
    if missing:
        raise SystemExit(f"{len(missing)} ids of the fold table are not rows of the data, e.g. "
                         f"{sorted(map(str, missing))[:3]}; make the folds from these rows")
    folds = {}
    for repeat, fold, rid, role in rows:
        f = folds.setdefault(repeat, {}).setdefault(fold, {"train": [], "test": []})
        f[role].append(index[rid])
    return {r: [(np.array(f["train"]), np.array(f["test"])) for _, f in sorted(fs.items())]
            for r, fs in sorted(folds.items())}


def simple_folds(n, scheme="rows", k=5, group=None, repeats=1):
    """A quick fold table in memory: rows split at random, or whole groups held out together."""
    from sklearn.model_selection import GroupKFold, KFold

    out = {}
    for r in range(repeats):
        if scheme == "group":
            if group is None:
                raise SystemExit("--cv group needs --group")
            codes = np.unique(group, return_inverse=True)[1]
            order = np.random.default_rng(r).permutation(codes.max() + 1)
            parts = GroupKFold(n_splits=k).split(np.zeros(n), groups=order[codes])
        else:
            parts = KFold(n_splits=k, shuffle=True, random_state=r).split(np.zeros(n))
        out[r] = [(tr, te) for tr, te in parts]
    return out


def run(y, X, group, names, folds, task):
    y, X = np.asarray(y), np.asarray(X, float)
    out = {}
    for name in names:
        if name == "group_mean" and group is None:
            raise SystemExit("group_mean needs --group")
        per = {}
        for repeat, splits in folds.items():
            pred = np.full(len(y), np.nan)
            for tr, te in splits:
                if not np.isnan(pred[te]).all():
                    raise SystemExit("a row is tested by two folds of one repeat")
                pred[te] = predict_fold(name, task, X[tr], y[tr], X[te],
                                        None if group is None else group[tr],
                                        None if group is None else group[te], seed=repeat)
            ok = ~np.isnan(pred)
            per.setdefault("n", []).append(int(ok.sum()))
            for k, v in score(y[ok], pred[ok], task).items():
                per.setdefault(k, []).append(v)
        out[name] = per
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--task", choices=["regression", "classification"], required=True)
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--folds-file", help="a fold table; without it, --cv makes a quick one")
    p.add_argument("--cv", choices=["rows", "group"], default="rows")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--group")
    a = p.parse_args()
    cols = [a.id, a.target, *a.features] + ([a.group] if a.group else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; drop them before "
                         "making the folds, so that the folds and the data are the same rows")
    nf = len(a.features)
    ids = np.array([r[0] for r in kept])
    y = np.array([r[1] for r in kept], float if a.task == "regression" else int)
    X = np.array([r[2:2 + nf] for r in kept], float)
    group = np.array([r[2 + nf] for r in kept]) if a.group else None
    folds = (load_folds(a.folds_file, ids) if a.folds_file
             else simple_folds(len(ids), a.cv, a.folds, group, a.repeats))
    print(f"rows: {len(rows)}, repeats: {list(folds)}")
    for name, s in run(y, X, group, a.models, folds, a.task).items():
        n = s.pop("n")
        print(f"{name:<11} n {min(n)}-{max(n)}  " +
              "  ".join(f"{k} {np.mean(v):.4g}" for k, v in s.items()))


if __name__ == "__main__":
    main()

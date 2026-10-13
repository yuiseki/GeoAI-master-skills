"""Out-of-fold scores of the baselines a model has to beat.

Baselines: the training mean, the training median, the training mean of the row's group (falling
back to the training mean for a group absent from training), and a linear regression on the
standardised features. Each row is predicted once, by a model fitted without it, and all
predictions are scored together (RMSE, MAE, R2).

Usage:
    uvx --with duckdb --with scikit-learn python baselines.py TABLE TARGET FEATURE [FEATURE ...] \
        --group COLUMN [--group-folds] [--folds 5] [--seed 0]

TABLE is anything DuckDB reads (a Parquet path or URL). Rows with a missing target or feature are
dropped, and the number dropped is printed.
"""

import argparse

import duckdb
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def scores(y, pred):
    err = y - pred
    ss_tot = ((y - y.mean()) ** 2).sum()
    return {
        "n": len(y),
        "rmse": float(np.sqrt((err**2).mean())),
        "mae": float(np.abs(err).mean()),
        "r2": float(1 - (err**2).sum() / ss_tot),
    }


def evaluate(y, X, group, folds, group_folds, seed):
    y, X, group = np.asarray(y, float), np.asarray(X, float), np.asarray(group)
    if group_folds:
        splits = GroupKFold(n_splits=folds).split(X, y, group)
    else:
        splits = KFold(n_splits=folds, shuffle=True, random_state=seed).split(X)

    names = ("mean", "median", "group_mean", "linear")
    pred = {k: np.full(len(y), np.nan) for k in names}
    for train, test in splits:
        yt = y[train]
        pred["mean"][test] = yt.mean()
        pred["median"][test] = np.median(yt)
        means = {g: yt[group[train] == g].mean() for g in np.unique(group[train])}
        pred["group_mean"][test] = [means.get(g, yt.mean()) for g in group[test]]
        model = make_pipeline(StandardScaler(), LinearRegression()).fit(X[train], yt)
        pred["linear"][test] = model.predict(X[test])

    for k in names:
        if np.isnan(pred[k]).any():
            raise SystemExit(f"{k}: some rows got no out-of-fold prediction")
    return {k: scores(y, pred[k]) for k in names}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--group", required=True)
    p.add_argument("--group-folds", action="store_true")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    cols = [a.target, *a.features, a.group]
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = duckdb.sql(f"select {quoted} from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    print(f"rows: {len(rows)}, dropped for a missing value: {len(rows) - len(kept)}")
    y = np.array([r[0] for r in kept], float)
    X = np.array([r[1:-1] for r in kept], float)
    group = np.array([r[-1] for r in kept])
    print(f"folds: {a.folds} {'by ' + a.group if a.group_folds else 'shuffled rows'}")

    for name, s in evaluate(y, X, group, a.folds, a.group_folds, a.seed).items():
        print(f"{name:<11} rmse {s['rmse']:.4g}  mae {s['mae']:.4g}  r2 {s['r2']:.3f}")


if __name__ == "__main__":
    main()

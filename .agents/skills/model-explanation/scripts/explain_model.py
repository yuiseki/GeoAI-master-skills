"""Explain what a model relies on, on held-out rows of the same fold table it is scored on.

    importance  permutation importance: in each fold, fit on the training rows, then shuffle one
                feature (or a --group of features together) among the test rows and record how
                much the score falls (R2 for regression, AUC for classification). Mean and sd
                over folds and repeats. Measured on held-out rows, so a feature the model only
                memorised costs nothing.
    pd          partial dependence: in each fold, set the feature to each grid value for every
                test row and average the predictions; the grid runs between the 5th and 95th
                percentiles, where there are data.
    ice         the same curve for each of a sample of rows (first repeat), summarised by how
                much each row's prediction changes over the grid: an average that hides
                opposite effects shows up as rows going both ways.

Models and folds come from compare_models.py, a copy of which sits in this directory.

Usage:
    uvx --with duckdb --with scikit-learn python explain_model.py importance TABLE ID TARGET F1 F2 ... \
        --task regression --model hgb --folds-file folds.parquet [--group lonlat=lon,lat ...]
    uvx --with duckdb --with scikit-learn python explain_model.py pd TABLE ID TARGET F1 F2 ... \
        --task regression --model hgb --folds-file folds.parquet --feature F1 [--points 11]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import r2_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_models import MODELS, load_folds  # noqa: E402


def _score(y, pred, task):
    return roc_auc_score(y, pred) if task == "classification" else r2_score(y, pred)


def _predict(model, X, task):
    return model.predict_proba(X)[:, 1] if task == "classification" else model.predict(X)


def permutation_importance(y, X, names, model_name, folds, task, groups=None, shuffles=5, seed=0):
    y, X = np.asarray(y), np.asarray(X, float)
    sets = {n: [i] for i, n in enumerate(names)}
    for g, members in (groups or {}).items():
        sets[g] = [names.index(m) for m in members]
    drops = {k: [] for k in sets}
    rng = np.random.default_rng(seed)
    for repeat, splits in folds.items():
        for train, test in splits:
            model = MODELS[model_name][task](repeat).fit(X[train], y[train])
            base = _score(y[test], _predict(model, X[test], task), task)
            for k, cols in sets.items():
                fold_drops = []
                for _ in range(shuffles):
                    Xp = X[test].copy()
                    perm = rng.permutation(len(test))
                    Xp[:, cols] = Xp[perm][:, cols]  # shuffle the set's columns together
                    fold_drops.append(base - _score(y[test], _predict(model, Xp, task), task))
                drops[k].append(float(np.mean(fold_drops)))
    return {k: {"mean": float(np.mean(v)), "sd": float(np.std(v))} for k, v in drops.items()}


def partial_dependence(y, X, j, model_name, folds, task, points=11):
    y, X = np.asarray(y), np.asarray(X, float)
    grid = np.linspace(*np.percentile(X[:, j], [5, 95]), points)
    curves = []
    for repeat, splits in folds.items():
        for train, test in splits:
            model = MODELS[model_name][task](repeat).fit(X[train], y[train])
            curve = []
            for v in grid:
                Xg = X[test].copy()
                Xg[:, j] = v
                curve.append(float(np.mean(_predict(model, Xg, task))))
            curves.append(curve)
    return grid, np.mean(curves, axis=0)


def ice_curves(y, X, j, model_name, folds, task, points=11, sample=200, seed=0):
    """Individual conditional expectation: for a random sample of rows, each row's prediction as
    feature j runs over the grid, from the model of the fold in which the row was held out (the
    first repeat). Returns the curves (rows x points) and the sampled row indices."""
    y, X = np.asarray(y), np.asarray(X, float)
    grid = np.linspace(*np.percentile(X[:, j], [5, 95]), points)
    repeat = sorted(folds)[0]
    rng = np.random.default_rng(seed)
    tested = np.concatenate([t for _, t in folds[repeat]])
    rows = np.sort(rng.choice(tested, size=min(sample, len(tested)), replace=False))
    curves = np.full((len(rows), points), np.nan)
    pos = {r: i for i, r in enumerate(rows)}
    for train, test in folds[repeat]:
        mine = [r for r in test if r in pos]
        if not mine:
            continue
        model = MODELS[model_name][task](repeat).fit(X[train], y[train])
        for k, v in enumerate(grid):
            Xg = X[mine].copy()
            Xg[:, j] = v
            curves[[pos[r] for r in mine], k] = _predict(model, Xg, task)
    return curves, rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["importance", "pd", "ice"])
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--task", choices=["regression", "classification"], required=True)
    p.add_argument("--model", required=True, choices=list(MODELS))
    p.add_argument("--folds-file", required=True)
    p.add_argument("--group", action="append", default=[],
                   help="NAME=F1,F2: also permute these features together")
    p.add_argument("--shuffles", type=int, default=5)
    p.add_argument("--feature")
    p.add_argument("--points", type=int, default=11)
    a = p.parse_args()

    import duckdb

    cols = [a.id, a.target, *a.features]
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("some rows have a missing value; drop them before making the folds")
    ids = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows], float if a.task == "regression" else int)
    X = np.array([r[2:] for r in rows], float)
    folds = load_folds(a.folds_file, ids)
    metric = "AUC" if a.task == "classification" else "R2"
    print(f"rows: {len(y)}, model: {a.model}, folds: {a.folds_file}, repeats: {list(folds)}")

    if a.kind == "importance":
        groups = {}
        for g in a.group:
            name, members = g.split("=", 1)
            groups[name] = members.split(",")
        imp = permutation_importance(y, X, a.features, a.model, folds, a.task, groups, a.shuffles)
        print(f"drop in {metric} when permuted on held-out rows (mean, sd over folds):")
        for k, v in sorted(imp.items(), key=lambda kv: -kv[1]["mean"]):
            print(f"  {k:<24} {v['mean']:+.3f}  (sd {v['sd']:.3f})")
    elif a.kind == "ice":
        if a.feature not in a.features:
            p.error("--feature must be one of the features")
        curves, rows = ice_curves(y, X, a.features.index(a.feature), a.model, folds, a.task, a.points)
        change = curves[:, -1] - curves[:, 0]
        q = np.percentile(change, [10, 50, 90])
        print(f"ICE of {a.feature}, {len(rows)} sampled rows: change of the prediction from the 5th to the"
              f" 95th percentile: 10th {q[0]:+.4g}, median {q[1]:+.4g}, 90th {q[2]:+.4g};"
              f" rows going down {int((change < 0).sum())}, up {int((change > 0).sum())}")
    else:
        if a.feature not in a.features:
            p.error("--feature must be one of the features")
        grid, pd = partial_dependence(y, X, a.features.index(a.feature), a.model, folds, a.task,
                                      a.points)
        print(f"partial dependence of the prediction on {a.feature} (5th to 95th percentile):")
        for v, m in zip(grid, pd):
            print(f"  {a.feature} {v:10.4g}  prediction {m:.4g}")


if __name__ == "__main__":
    main()

"""Compare models on the same folds, out of fold, over several seeds.

Every row is predicted once per seed, by a model fitted without it, and all predictions of a seed
are scored together. Anything a model tunes (Ridge's penalty, the boosting's early stopping) is
chosen inside the training rows of the fold, never on the held-out rows.

Regression scores: rmse, mae, r2. Classification (binary): log_loss, brier, auc, accuracy.

Models (regression / classification):
    mean / prior     the training mean, or the training class share
    group_mean       the training mean of the row's group (needs --group)
    linear           linear regression / logistic regression, on standardised features
    ridge            RidgeCV / LogisticRegressionCV, penalty chosen by inner CV on the training rows
    rf               random forest, 500 trees
    hgb              histogram gradient boosting, early stopping on 10% of the training rows

Usage:
    uvx --with duckdb --with scikit-learn python compare_models.py TABLE TARGET FEATURE [...] \
        --task regression|classification --models mean linear rf hgb \
        [--group COLUMN] [--group-folds] [--folds 5] [--seeds 0 1 2]
"""

import argparse

import duckdb
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import (
    LinearRegression,
    LogisticRegression,
    LogisticRegressionCV,
    RidgeCV,
)
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class Constant(BaseEstimator, RegressorMixin):
    def fit(self, X, y):
        self.value_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class Prior(BaseEstimator, ClassifierMixin):
    def fit(self, X, y):
        self.p_ = float(np.mean(y))
        return self

    def predict_proba(self, X):
        return np.c_[np.full(len(X), 1 - self.p_), np.full(len(X), self.p_)]


class GroupMean(BaseEstimator, RegressorMixin):
    """Mean of the training rows of the same group; the last column of X is the group code."""

    def fit(self, X, y):
        g = X[:, -1]
        self.overall_ = float(np.mean(y))
        self.means_ = {k: float(np.mean(y[g == k])) for k in np.unique(g)}
        return self

    def predict(self, X):
        return np.array([self.means_.get(k, self.overall_) for k in X[:, -1]])


def scaled(model):
    return lambda seed: make_pipeline(StandardScaler(), model(seed))


MODELS = {
    "mean": {"regression": lambda seed: Constant()},
    "prior": {"classification": lambda seed: Prior()},
    "group_mean": {"regression": lambda seed: GroupMean()},
    "linear": {
        "regression": scaled(lambda seed: LinearRegression()),
        "classification": scaled(lambda seed: LogisticRegression(C=1e6, max_iter=5000)),
    },
    "ridge": {
        "regression": scaled(lambda seed: RidgeCV(alphas=np.logspace(-3, 3, 13))),
        "classification": scaled(lambda seed: LogisticRegressionCV(
            Cs=13, l1_ratios=(0,), scoring="neg_log_loss", max_iter=5000, use_legacy_attributes=False)),
    },
    "rf": {
        "regression": lambda seed: RandomForestRegressor(n_estimators=500, random_state=seed, n_jobs=-1),
        "classification": lambda seed: RandomForestClassifier(n_estimators=500, random_state=seed, n_jobs=-1),
    },
    "hgb": {
        "regression": lambda seed: HistGradientBoostingRegressor(
            early_stopping=True, validation_fraction=0.1, random_state=seed),
        "classification": lambda seed: HistGradientBoostingClassifier(
            early_stopping=True, validation_fraction=0.1, random_state=seed),
    },
}


def make_splits(X, y, group, folds, group_folds, seed, task):
    if group_folds:
        return list(GroupKFold(n_splits=folds).split(X, y, group))
    if task == "classification":
        return list(StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed).split(X, y))
    return list(KFold(n_splits=folds, shuffle=True, random_state=seed).split(X))


def oof_predict(make_model, X, y, splits, task):
    pred = np.full(len(y), np.nan)
    for train, test in splits:
        model = make_model().fit(X[train], y[train])
        if task == "classification":
            pred[test] = model.predict_proba(X[test])[:, 1]
        else:
            pred[test] = model.predict(X[test])
    if np.isnan(pred).any():
        raise SystemExit("some rows got no out-of-fold prediction")
    return pred


def score(y, pred, task):
    if task == "classification":
        p = np.clip(pred, 1e-15, 1 - 1e-15)
        return {
            "log_loss": log_loss(y, p, labels=[0, 1]),
            "brier": brier_score_loss(y, p),
            "auc": roc_auc_score(y, p) if len(np.unique(y)) == 2 else float("nan"),
            "accuracy": accuracy_score(y, p >= 0.5),
        }
    return {
        "rmse": float(np.sqrt(np.mean((y - pred) ** 2))),
        "mae": mean_absolute_error(y, pred),
        "r2": r2_score(y, pred),
    }


def run(y, X, group, names, folds, group_folds, seeds, task):
    y, X = np.asarray(y), np.asarray(X, float)
    if task == "classification" and set(np.unique(y)) - {0, 1}:
        raise SystemExit("classification takes a 0/1 target")
    if group is not None:
        codes = np.unique(np.asarray(group), return_inverse=True)[1].astype(float)
    out = {}
    for name in names:
        if task not in MODELS[name]:
            raise SystemExit(f"{name} does not do {task}")
        Xm = X
        if name == "group_mean":
            if group is None:
                raise SystemExit("group_mean needs --group")
            Xm = np.c_[X, codes]
        per_seed = {}
        for seed in seeds:
            # Group folds do not depend on the seed; the seed then varies the models only.
            splits = make_splits(Xm, y, group, folds, group_folds, seed, task)
            pred = oof_predict(lambda: MODELS[name][task](seed), Xm, y, splits, task)
            for k, v in score(y, pred, task).items():
                per_seed.setdefault(k, []).append(v)
        out[name] = per_seed
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--task", choices=["regression", "classification"], required=True)
    p.add_argument("--models", nargs="+", required=True, choices=list(MODELS))
    p.add_argument("--group")
    p.add_argument("--group-folds", action="store_true")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    a = p.parse_args()
    if a.group_folds and not a.group:
        p.error("--group-folds needs --group")

    cols = [a.target, *a.features] + ([a.group] if a.group else [])
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = duckdb.sql(f"select {quoted} from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    print(f"rows: {len(rows)}, dropped for a missing value: {len(rows) - len(kept)}")
    nf = len(a.features)
    y = np.array([r[0] for r in kept], float if a.task == "regression" else int)
    X = np.array([r[1:1 + nf] for r in kept], float)
    group = np.array([r[-1] for r in kept]) if a.group else None
    print(f"folds: {a.folds} {'by ' + a.group if a.group_folds else 'shuffled'}, seeds: {a.seeds}")

    for name, s in run(y, X, group, a.models, a.folds, a.group_folds, a.seeds, a.task).items():
        cells = "  ".join(
            f"{k} {np.mean(v):.4g} (sd {np.std(v):.2g})" for k, v in s.items()
        )
        print(f"{name:<11} {cells}")


if __name__ == "__main__":
    main()

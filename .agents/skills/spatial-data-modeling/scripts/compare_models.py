"""Compare models on the same folds, out of fold, over several repeats.

The folds come from a fold table made by cross-validation-design/scripts/make_folds.py, so that
baselines and models are scored on the same folds. In each repeat every tested row is predicted
once, by a model fitted without it, and the repeat's predictions are scored together; rows the
repeat never tests (the first periods of time folds) are left out of the score, and n says how many
were scored. The repeat number also seeds the models.

Anything a model tunes (Ridge's penalty, the boosting's early stopping) is chosen inside the
training rows of the fold, never on the held-out rows.

Regression scores: rmse, mae, r2. Classification (binary): log_loss, brier, auc, accuracy.

Models (regression / classification):
    mean / prior     the training mean, or the training class share
    median           the training median
    group_mean       the training mean of the row's group (needs --group)
    linear           linear regression / logistic regression, on standardised features
    ridge            RidgeCV / LogisticRegressionCV, penalty chosen by inner CV on the training rows
    rf               random forest, 500 trees
    hgb              histogram gradient boosting, early stopping on 10% of the training rows
    tabpfn_v2        TabPFN v2 on the CPU, weights pinned to a commercially usable version
                     (needs --with tabpfn==9.1.0; see references/foundation-modeling.md)

Usage:
    uvx --with duckdb --with scikit-learn python compare_models.py TABLE ID TARGET FEATURE [...] \
        --task regression|classification --models mean linear rf hgb \
        --folds-file folds.parquet [--group COLUMN]

TABLE must have no missing value in the columns used, and the folds must be made from the same
rows.
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
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class Constant(BaseEstimator, RegressorMixin):
    def fit(self, X, y):
        self.value_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class Median(BaseEstimator, RegressorMixin):
    def fit(self, X, y):
        self.value_ = float(np.median(y))
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
    "median": {"regression": lambda seed: Median()},
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
    "tabpfn_v2": {
        "regression": lambda seed: tabpfn_v2("regression", seed),
        "classification": lambda seed: tabpfn_v2("classification", seed),
    },
}

# TabPFN v2 weights under the Prior Labs License 1.1 (Apache 2.0 plus an attribution clause).
# Later versions (2.5 onwards) forbid commercial use, and the tabpfn package defaults to the latest,
# so the version, the file and the Hugging Face commit are all fixed here.
TABPFN_V2_WEIGHTS = {
    "regression": ("Prior-Labs/TabPFN-v2-reg", "tabpfn-v2-regressor.ckpt",
                   "4972a65a1b30806315c6f92499959ffbfc69a673"),
    "classification": ("Prior-Labs/TabPFN-v2-clf", "tabpfn-v2-classifier-finetuned-zk73skhh.ckpt",
                       "f851f2a3c941544733b712d8c0f96dfae9b28862"),
}


def tabpfn_v2(task, seed):
    # Imported here so that the other models need neither torch nor tabpfn.
    from huggingface_hub import hf_hub_download
    from tabpfn import TabPFNClassifier, TabPFNRegressor
    from tabpfn.constants import ModelVersion

    repo, filename, revision = TABPFN_V2_WEIGHTS[task]
    path = hf_hub_download(repo, filename, revision=revision)
    cls = TabPFNRegressor if task == "regression" else TabPFNClassifier
    return cls.create_default_for_version(
        ModelVersion.V2, model_path=path, device="cpu", random_state=seed)


def load_folds(path, ids):
    """{repeat: [(train indices, test indices), ...]} from a fold table made by make_folds.py.

    Every id in the fold table must be a row of the data: the folds have to be made from the
    same rows, after any row with a missing value has been dropped.
    """
    index = {v: i for i, v in enumerate(ids.tolist())}
    rows = duckdb.sql(f"select repeat, fold, id, role from '{path}' order by all").fetchall()
    missing = {r[2] for r in rows if r[2] not in index}
    if missing:
        raise SystemExit(f"{len(missing)} ids of the fold table are not rows of the data, "
                         f"e.g. {sorted(map(str, missing))[:3]}; make the folds from these rows")
    folds = {}
    for repeat, fold, rid, role in rows:
        f = folds.setdefault(repeat, {}).setdefault(fold, {"train": [], "test": []})
        f[role].append(index[rid])
    return {r: [(np.array(f["train"]), np.array(f["test"])) for _, f in sorted(fs.items())]
            for r, fs in sorted(folds.items())}


def oof_predict(make_model, X, y, splits, task):
    """Out-of-fold predictions; NaN for a row no fold tests."""
    pred = np.full(len(y), np.nan)
    for train, test in splits:
        if not np.isnan(pred[test]).all():
            raise SystemExit("a row is tested by two folds of one repeat")
        model = make_model().fit(X[train], y[train])
        if task == "classification":
            pred[test] = model.predict_proba(X[test])[:, 1]
        else:
            pred[test] = model.predict(X[test])
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


def run(y, X, group, names, folds, task):
    """Scores per model, one value per repeat, on the rows the repeat tests.

    folds: {repeat: [(train, test), ...]}. The repeat also seeds the models.
    """
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
        per_repeat = {}
        for repeat, splits in folds.items():
            pred = oof_predict(lambda: MODELS[name][task](repeat), Xm, y, splits, task)
            tested = ~np.isnan(pred)
            per_repeat.setdefault("n", []).append(int(tested.sum()))
            for k, v in score(y[tested], pred[tested], task).items():
                per_repeat.setdefault(k, []).append(v)
        out[name] = per_repeat
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--task", choices=["regression", "classification"], required=True)
    p.add_argument("--models", nargs="+", required=True, choices=list(MODELS))
    p.add_argument("--folds-file", required=True)
    p.add_argument("--group")
    a = p.parse_args()

    cols = [a.id, a.target, *a.features] + ([a.group] if a.group else [])
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = duckdb.sql(f"select {quoted} from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; drop them before "
                         "making the folds, so that the folds and the data are the same rows")
    nf = len(a.features)
    ids = np.array([r[0] for r in kept])
    y = np.array([r[1] for r in kept], float if a.task == "regression" else int)
    X = np.array([r[2:2 + nf] for r in kept], float)
    group = np.array([r[-1] for r in kept]) if a.group else None
    folds = load_folds(a.folds_file, ids)
    print(f"rows: {len(rows)}, folds: {a.folds_file}, repeats: {list(folds)}")

    for name, s in run(y, X, group, a.models, folds, a.task).items():
        n = s.pop("n")
        cells = "  ".join(f"{k} {np.mean(v):.4g} (sd {np.std(v):.2g})" for k, v in s.items())
        print(f"{name:<11} n {min(n)}-{max(n)}  {cells}")


if __name__ == "__main__":
    main()

"""Compare models on the same folds, out of fold, over several repeats.

The folds come from a fold table (repeat, fold, id, role; one Parquet file), so that
baselines and models are scored on the same folds. In each repeat every tested row is predicted
once, by a model fitted without it, and the repeat's predictions are scored together; rows the
repeat never tests (the first periods of time folds) are left out of the score, and n says how many
were scored. The repeat number also seeds the models.

Anything a model tunes (ridge's penalty, the boosting's number of iterations) is chosen inside the
training rows of the fold, never on the held-out rows, and on inner folds that keep the dependence the
outer folds keep: for outer fold k, each other fold j gives the inner split (fold j's training rows,
fold j's test rows), both cut to fold k's training rows. Held-out groups, spatial blocks and their
buffers, and earlier-periods-only carry over. Standardising is part of each candidate, so it is fitted
on the inner training rows. The first fold of time folds has no earlier fold inside its training rows;
give --inner-time COLUMN, and the inner folds are then each of the last --inner-folds periods of the
training rows, trained on the periods before it minus --inner-gap.

Regression scores: rmse, mae, r2. Classification (binary, a 0/1 target): log_loss, brier, auc, accuracy.
Classification with any other labels (three or more classes, or text) is multiclass: each model gives a
probability for every class, the predicted class is the one with the highest probability (argmax, no
threshold), and the scores are log_loss, accuracy, balanced_accuracy, macro_f1, weighted_f1, and
precision[c], recall[c], f1[c] for each class c. A class absent from a fold's training rows gets
probability 0 there (clipped for the log loss), not a missing column. prior predicts the training class
shares; its argmax is the majority class, so its accuracy is the majority-class baseline.

Models (regression / classification):
    mean / prior     the training mean, or the training class share
    median           the training median
    group_mean       the training mean of the row's group (needs --group)
    linear           linear regression / logistic regression, on standardised features
    ridge            ridge / L2 logistic regression on standardised features, penalty chosen on the
                     inner folds (13 values, squared error / log loss pooled over the inner folds)
    rf               random forest, 500 trees
    hgb              histogram gradient boosting, at most 100 iterations, the number chosen on the
                     inner folds
    tabpfn_v2        TabPFN v2 on the CPU, weights pinned to a commercially usable version
                     (needs --with tabpfn==9.1.0; see references/foundation-modeling.md)

Usage:
    uvx --with duckdb --with scikit-learn python compare_models.py TABLE ID TARGET FEATURE [...] \
        --task regression|classification --models mean linear rf hgb \
        --folds-file folds.parquet [--group COLUMN] [--weight COLUMN] \
        [--inner-time COLUMN [--inner-folds 3] [--inner-gap 0]]

TABLE must have no missing value in the columns used, and the folds must be made from the same
rows.
"""

import argparse
import inspect

import duckdb
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _weighted_median(y, w):
    order = np.argsort(y)
    cum = np.cumsum(w[order])
    return float(y[order][np.searchsorted(cum, cum[-1] / 2)])


class Constant(BaseEstimator, RegressorMixin):
    def fit(self, X, y, sample_weight=None):
        self.value_ = float(np.average(y, weights=sample_weight))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class Median(BaseEstimator, RegressorMixin):
    def fit(self, X, y, sample_weight=None):
        w = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, float)
        self.value_ = _weighted_median(np.asarray(y, float), w)
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class Prior(BaseEstimator, ClassifierMixin):
    def fit(self, X, y, sample_weight=None):
        self.classes_ = np.unique(y)
        if set(self.classes_.tolist()) <= {0, 1}:  # binary: always both columns, as before
            self.classes_ = np.array([0, 1])
        w = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, float)
        self.shares_ = np.array([w[y == c].sum() for c in self.classes_]) / w.sum()
        return self

    def predict_proba(self, X):
        return np.tile(self.shares_, (len(X), 1))


class GroupMean(BaseEstimator, RegressorMixin):
    """Mean of the training rows of the same group; the last column of X is the group code."""

    def fit(self, X, y, sample_weight=None):
        g = X[:, -1]
        w = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, float)
        self.overall_ = float(np.average(y, weights=w))
        self.means_ = {k: float(np.average(y[g == k], weights=w[g == k])) for k in np.unique(g)}
        return self

    def predict(self, X):
        return np.array([self.means_.get(k, self.overall_) for k in X[:, -1]])


def _class_columns(est, X, classes):
    """Probabilities in the columns of classes, whatever subset of them est saw."""
    out = np.zeros((len(X), len(classes)))
    out[:, np.searchsorted(classes, est.classes_)] = est.predict_proba(X)
    return out


def _inner_loss(task, y, pred, classes, w):
    """Summed (weighted) squared error, or log loss with pred as columns of classes."""
    w = np.ones(len(y)) if w is None else w
    if task == "regression":
        return float(np.sum(w * (y - pred) ** 2))
    p = np.clip(pred[np.arange(len(y)), np.searchsorted(classes, y)], 1e-15, 1)
    return float(-np.sum(w * np.log(p)))


class InnerSearch(BaseEstimator):
    """Choose a parameter from grid on given inner splits, then refit on all the rows.

    make(param) builds a candidate (a pipeline when it standardises, so that the scaler is
    fitted with the candidate on the inner training rows). The loss is pooled over the inner
    validation rows: squared error for regression, log loss for classification.
    """

    uses_inner_splits = True

    def __init__(self, make, grid, task):
        self.make, self.grid, self.task = make, grid, task

    def _losses(self, X, y, w, inner):
        return [sum(self._split_loss(param, X, y, w, tr, va) for tr, va in inner) for param in self.grid]

    def _split_loss(self, param, X, y, w, tr, va):
        model = _fit(self.make(param), X[tr], y[tr], None if w is None else w[tr])
        pred = model.predict(X[va]) if self.task == "regression" else _class_columns(model, X[va], self.classes_)
        return _inner_loss(self.task, y[va], pred, getattr(self, "classes_", None), None if w is None else w[va])

    def fit(self, X, y, sample_weight=None, inner=None):
        if not inner:
            raise SystemExit("no inner folds to tune on")
        if self.task == "classification":
            self.classes_ = np.unique(y)
        losses = self._losses(X, y, sample_weight, inner)
        self.best_param_ = self.grid[int(np.argmin(losses))]
        self.model_ = _fit(self.make(self.best_param_), X, y, sample_weight)
        return self

    def predict(self, X):
        return self.model_.predict(X)

    def predict_proba(self, X):
        return _class_columns(self.model_, X, self.classes_)


class StagedSearch(InnerSearch):
    """Boosting: the number of iterations (1 .. max_iter) chosen on the inner splits from the
    staged predictions of one fit per split, then a refit with that number."""

    def __init__(self, make, max_iter, task):
        super().__init__(make, list(range(1, max_iter + 1)), task)
        self.max_iter = max_iter

    def _losses(self, X, y, w, inner):
        total = np.zeros(self.max_iter)
        for tr, va in inner:
            model = _fit(self.make(self.max_iter), X[tr], y[tr], None if w is None else w[tr])
            wv = None if w is None else w[va]
            if self.task == "regression":
                stages = model.staged_predict(X[va])
            else:
                stages = self._staged_columns(model, X[va])
            for i, pred in enumerate(stages):
                total[i] += _inner_loss(self.task, y[va], pred, getattr(self, "classes_", None), wv)
        return total

    def _staged_columns(self, model, X):
        cols = np.searchsorted(self.classes_, model.classes_)
        for p in model.staged_predict_proba(X):
            out = np.zeros((len(X), len(self.classes_)))
            out[:, cols] = p
            yield out


def scaled(model):
    return lambda seed: make_pipeline(StandardScaler(), model(seed))


def _hgb(task, seed):
    cls = HistGradientBoostingRegressor if task == "regression" else HistGradientBoostingClassifier
    return StagedSearch(lambda n: cls(max_iter=n, early_stopping=False, random_state=seed), 100, task)


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
        "regression": lambda seed: InnerSearch(
            lambda a: make_pipeline(StandardScaler(), Ridge(alpha=a)), list(np.logspace(-3, 3, 13)), "regression"),
        "classification": lambda seed: InnerSearch(
            lambda c: make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=5000)),
            list(np.logspace(-4, 4, 13)), "classification"),
    },
    "rf": {
        "regression": lambda seed: RandomForestRegressor(n_estimators=500, random_state=seed, n_jobs=-1),
        "classification": lambda seed: RandomForestClassifier(n_estimators=500, random_state=seed, n_jobs=-1),
    },
    "hgb": {
        "regression": lambda seed: _hgb("regression", seed),
        "classification": lambda seed: _hgb("classification", seed),
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


def effective_n(w):
    """Kish's effective sample size: as many equally weighted rows as these weights are worth."""
    w = np.asarray(w, float)
    return float(w.sum() ** 2 / (w ** 2).sum())


def inner_splits(splits, k):
    """Inner splits for outer fold k, as positions within its training rows: for each other fold
    j, (fold j's training rows, fold j's test rows), both cut to fold k's training rows. Folds
    that leave either side empty are skipped."""
    train = splits[k][0]
    pos = {r: i for i, r in enumerate(train.tolist())}
    out = []
    for j, (tr, te) in enumerate(splits):
        if j == k:
            continue
        itr = np.array([pos[r] for r in tr.tolist() if r in pos], int)
        ite = np.array([pos[r] for r in te.tolist() if r in pos], int)
        if len(itr) and len(ite):
            out.append((itr, ite))
    return out


def time_inner_splits(time, folds=3, gap=0):
    """Inner splits from time values of the training rows: each of the last folds distinct
    periods validated in turn, trained on the periods before it minus gap."""
    time = np.asarray(time)
    periods = np.unique(time)
    out = []
    for i in range(max(1, len(periods) - folds), len(periods)):
        tr = np.flatnonzero(time < periods[max(0, i - gap)]) if i - gap > 0 else np.array([], int)
        if len(tr):
            out.append((tr, np.flatnonzero(time == periods[i])))
    return out


def _fit(model, X, y, w, inner=None):
    """Fit, passing sample weights to the final step of a pipeline; refuse a model that cannot
    take them rather than silently fitting it unweighted. A model that tunes gets the inner
    splits."""
    if getattr(model, "uses_inner_splits", False):
        return model.fit(X, y, sample_weight=w, inner=inner)
    if w is None:
        return model.fit(X, y)
    est = model.steps[-1][1] if hasattr(model, "steps") else model
    if "sample_weight" not in inspect.signature(est.fit).parameters:
        raise SystemExit(f"{type(est).__name__} cannot be fitted with sample weights")
    if hasattr(model, "steps"):
        return model.fit(X, y, **{f"{model.steps[-1][0]}__sample_weight": w})
    return model.fit(X, y, sample_weight=w)


def _proba(model, X, n_classes):
    """Class probabilities in the columns 0 .. n_classes - 1, whatever classes the model saw."""
    est = model.steps[-1][1] if hasattr(model, "steps") else model
    out = np.zeros((len(X), n_classes))
    out[:, np.asarray(est.classes_, int)] = model.predict_proba(X)
    return out


def fit_fold(make_model, X, y, splits, k, weights=None, inner_time=None, inner_folds=3, inner_gap=0):
    """The model of outer fold k, fitted on its training rows; a model that tunes does so on
    inner_splits of the fold table, or on time_inner_splits of inner_time."""
    train = splits[k][0]
    model = make_model()
    inner = None
    if getattr(model, "uses_inner_splits", False):
        inner = (time_inner_splits(inner_time[train], inner_folds, inner_gap) if inner_time is not None
                 else inner_splits(splits, k))
        if not inner:
            raise SystemExit(f"fold {k} has no other fold inside its training rows to tune on (the first "
                             "fold of time folds); give --inner-time")
    return _fit(model, X[train], y[train], None if weights is None else weights[train], inner)


def oof_predict(make_model, X, y, splits, task, weights=None, n_classes=None, inner_time=None,
                inner_folds=3, inner_gap=0):
    """Out-of-fold predictions; NaN for a row no fold tests. With n_classes (multiclass, y coded
    0 .. n_classes - 1), one row of class probabilities per data row. Each fold's model comes from
    fit_fold."""
    pred = np.full(len(y) if n_classes is None else (len(y), n_classes), np.nan)
    for k, (train, test) in enumerate(splits):
        if not np.isnan(pred[test]).all():
            raise SystemExit("a row is tested by two folds of one repeat")
        model = fit_fold(make_model, X, y, splits, k, weights, inner_time, inner_folds, inner_gap)
        if n_classes is not None:
            pred[test] = _proba(model, X[test], n_classes)
        elif task == "classification":
            pred[test] = model.predict_proba(X[test])[:, 1]
        else:
            pred[test] = model.predict(X[test])
    return pred


def score_multiclass(y, proba, labels=None, weights=None):
    """y coded 0 .. K - 1, proba (n, K). Labels name the classes in the per-class keys."""
    k = proba.shape[1]
    labels = list(range(k)) if labels is None else list(labels)
    p = np.clip(proba, 1e-15, 1)
    p = p / p.sum(1, keepdims=True)
    hat = proba.argmax(1)
    ks = list(range(k))
    prec, rec, f1, _ = precision_recall_fscore_support(y, hat, labels=ks, sample_weight=weights, zero_division=0)
    out = {
        "log_loss": log_loss(y, p, labels=ks, sample_weight=weights),
        "accuracy": accuracy_score(y, hat, sample_weight=weights),
        "balanced_accuracy": float(np.mean([r for r, c in zip(rec, ks) if np.any(y == c)])),
        "macro_f1": f1_score(y, hat, labels=ks, average="macro", sample_weight=weights, zero_division=0),
        "weighted_f1": f1_score(y, hat, labels=ks, average="weighted", sample_weight=weights, zero_division=0),
    }
    for name, values in (("precision", prec), ("recall", rec), ("f1", f1)):
        for lab, v in zip(labels, values):
            out[f"{name}[{lab}]"] = float(v)
    return out


def score(y, pred, task, weights=None, labels=None):
    w = weights
    if task == "classification" and np.ndim(pred) == 2:
        return score_multiclass(np.asarray(y), np.asarray(pred, float), labels, w)
    if task == "classification":
        p = np.clip(pred, 1e-15, 1 - 1e-15)
        return {
            "log_loss": log_loss(y, p, labels=[0, 1], sample_weight=w),
            "brier": brier_score_loss(y, p, sample_weight=w),
            "auc": roc_auc_score(y, p, sample_weight=w) if len(np.unique(y)) == 2 else float("nan"),
            "accuracy": accuracy_score(y, p >= 0.5, sample_weight=w),
        }
    return {
        "rmse": float(np.sqrt(np.average((y - pred) ** 2, weights=w))),
        "mae": mean_absolute_error(y, pred, sample_weight=w),
        "r2": r2_score(y, pred, sample_weight=w),
    }


def run(y, X, group, names, folds, task, predictions=None, weights=None, inner_time=None,
        inner_folds=3, inner_gap=0):
    """Scores per model, one value per repeat, on the rows the repeat tests.

    folds: {repeat: [(train, test), ...]}. The repeat also seeds the models.
    predictions: if a list, (repeat, model, row index, prediction) is appended for every tested row.
    weights: per-row weights, used both to fit (sample_weight) and to score.
    inner_time: per-row time values; tuning models then tune on time_inner_splits.
    """
    y, X = np.asarray(y), np.asarray(X, float)
    labels, n_classes = None, None
    if task == "classification" and set(np.unique(y).tolist()) - {0, 1}:
        labels, y = np.unique(y, return_inverse=True)
        n_classes = len(labels)
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
            pred = oof_predict(lambda: MODELS[name][task](repeat), Xm, y, splits, task, weights, n_classes,
                               inner_time, inner_folds, inner_gap)
            tested = ~np.isnan(pred) if n_classes is None else ~np.isnan(pred).any(1)
            if predictions is not None and n_classes is None:
                predictions.extend((repeat, name, int(i), float(pred[i]))
                                   for i in np.flatnonzero(tested))
            elif predictions is not None:
                predictions.extend((repeat, name, int(i), float(pred[i, c]), str(labels[c]))
                                   for i in np.flatnonzero(tested) for c in range(n_classes))
            per_repeat.setdefault("n", []).append(int(tested.sum()))
            wt = None if weights is None else weights[tested]
            for k, v in score(y[tested], pred[tested], task, wt, labels).items():
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
    p.add_argument("--weight", help="a column of per-row weights, used to fit and to score")
    p.add_argument("--inner-time", help="a column: tune on the last --inner-folds periods of each fold's "
                                        "training rows instead of on the other folds")
    p.add_argument("--inner-folds", type=int, default=3)
    p.add_argument("--inner-gap", type=int, default=0, help="periods left out before each inner test period")
    p.add_argument("--predictions-out",
                   help="write the out-of-fold predictions (repeat, model, id, target, prediction); "
                        "needs --with pyarrow")
    a = p.parse_args()

    cols = [a.id, a.target, *a.features] + ([a.group] if a.group else []) \
        + ([a.inner_time] if a.inner_time else []) + ([a.weight] if a.weight else [])
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = duckdb.sql(f"select {quoted} from '{a.table}'").fetchall()
    kept = [r for r in rows if all(v is not None for v in r)]
    if len(kept) != len(rows):
        raise SystemExit(f"{len(rows) - len(kept)} rows have a missing value; drop them before "
                         "making the folds, so that the folds and the data are the same rows")
    nf = len(a.features)
    ids = np.array([r[0] for r in kept])
    y = np.array([r[1] for r in kept])
    if a.task == "regression":
        y = y.astype(float)
    elif set(np.unique(y).tolist()) <= {0, 1}:
        y = y.astype(int)
    X = np.array([r[2:2 + nf] for r in kept], float)
    gi = 2 + nf
    group = np.array([r[gi] for r in kept]) if a.group else None
    inner_time = np.array([r[gi + bool(a.group)] for r in kept]) if a.inner_time else None
    weights = np.array([r[-1] for r in kept], float) if a.weight else None
    if weights is not None and (weights < 0).any():
        raise SystemExit("weights must not be negative")
    folds = load_folds(a.folds_file, ids)
    print(f"rows: {len(rows)}, folds: {a.folds_file}, repeats: {list(folds)}")

    preds = [] if a.predictions_out else None
    if weights is not None:
        print(f"weighted by {a.weight} (fit and score), effective rows {effective_n(weights):.1f}"
              f" of {len(weights)}")
    for name, s in run(y, X, group, a.models, folds, a.task, preds, weights, inner_time, a.inner_folds,
                       a.inner_gap).items():
        n = s.pop("n")
        cells = "  ".join(f"{k} {np.mean(v):.4g} (sd {np.std(v):.2g})" for k, v in s.items())
        print(f"{name:<11} n {min(n)}-{max(n)}  {cells}")

    if preds is not None:
        import pyarrow as pa  # only needed here: --with pyarrow

        cols = {
            "repeat": [r[0] for r in preds],
            "model": [r[1] for r in preds],
            "id": [str(ids[r[2]]) for r in preds],
            "target": [str(y[r[2]]) if len(r) == 5 else float(y[r[2]]) for r in preds],
            "prediction": [r[3] for r in preds],
        }
        if preds and len(preds[0]) == 5:  # multiclass: one row per class, prediction is its probability
            cols["class"] = [r[4] for r in preds]
        pred_rows = pa.table(cols)
        duckdb.sql(f"copy (select * from pred_rows order by all) to '{a.predictions_out}' "
                   "(format parquet)")
        print(f"predictions: {len(preds)} rows to {a.predictions_out}")


if __name__ == "__main__":
    main()

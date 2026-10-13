"""Look for leaks in the features of a table, on the same fold table the models are scored on.

Four checks:
    single feature    each feature alone, in a gradient boosting model. A feature that alone scores
                      at or above --flag-score (R2, or AUC for classification) may restate the target.
    identifies group  with --group, a feature that is constant within each group and takes a
                      different value in each group can stand in for the group's identity, letting a
                      model memorise units (codes, a unit's fixed coordinates).
    permuted target   the full model on a target shuffled within each repeat. With an honest
                      pipeline it scores about nothing; a clear score means something outside the
                      features leaks (preprocessing fitted on all rows, duplicated rows).
    duplicates        test rows whose feature values equal a training row's exactly.

Usage:
    uvx --with duckdb --with scikit-learn python audit_features.py TABLE ID TARGET FEATURE [...] \
        --task regression|classification --folds-file folds.parquet [--group COL] [--flag-score 0.9]

Scoring and folds come from spatial-data-modeling/scripts/compare_models.py.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "spatial-data-modeling" / "scripts"))
from compare_models import load_folds, run  # noqa: E402


def headline(task):
    return "r2" if task == "regression" else "auc"


def audit(y, X, names, group, folds, task, flag_score=0.9, seed=0):
    y, X = np.asarray(y), np.asarray(X, float)
    key = headline(task)
    out = {}

    real = run(y, X, None, ["hgb"], folds, task)["hgb"]
    out["real"] = {key: float(np.mean(real[key]))}

    singles = []
    for j, name in enumerate(names):
        s = run(y, X[:, [j]], None, ["hgb"], folds, task)["hgb"]
        v = float(np.mean(s[key]))
        singles.append({"feature": name, key: v, "flag": v >= flag_score})
    out["single_feature"] = sorted(singles, key=lambda f: -f[key])

    if group is not None:
        group = np.asarray(group)
        n_groups = len(np.unique(group))
        ident = []
        for j, name in enumerate(names):
            per_group = {}
            for g, v in zip(group, X[:, j]):
                per_group.setdefault(g, set()).add(v)
            constant = all(len(v) == 1 for v in per_group.values())
            distinct = len({next(iter(v)) for v in per_group.values()}) if constant else 0
            ident.append({"feature": name, "constant_within_group": constant,
                          "distinct_over_groups": distinct,
                          "flag": constant and distinct == n_groups and n_groups > 1})
        out["identifies_group"] = ident

    rng = np.random.default_rng(seed)
    y_perm = rng.permutation(y)
    perm = run(y_perm, X, None, ["hgb"], folds, task)["hgb"]
    out["permuted"] = {key: float(np.mean(perm[key]))}

    twins = 0
    tested = 0
    for splits in folds.values():
        for train, test in splits:
            seen = {tuple(r) for r in X[train]}
            twins += sum(tuple(r) in seen for r in X[test])
            tested += len(test)
    out["duplicates"] = {"test_rows_with_a_train_twin": twins, "test_rows": tested}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("features", nargs="+")
    p.add_argument("--task", choices=["regression", "classification"], required=True)
    p.add_argument("--folds-file", required=True)
    p.add_argument("--group")
    p.add_argument("--flag-score", type=float, default=0.9)
    a = p.parse_args()

    import duckdb

    cols = [a.id, a.target, *a.features] + ([a.group] if a.group else [])
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = duckdb.sql(f"select {quoted} from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("some rows have a missing value; drop them before making the folds")
    nf = len(a.features)
    ids = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows], float if a.task == "regression" else int)
    X = np.array([r[2:2 + nf] for r in rows], float)
    group = np.array([r[-1] for r in rows]) if a.group else None
    r = audit(y, X, a.features, group, load_folds(a.folds_file, ids), a.task, a.flag_score)

    key = headline(a.task)
    print(f"all features: {key} {r['real'][key]:.3f}")
    print(f"single feature ({key}, flag at {a.flag_score}):")
    for f in r["single_feature"]:
        print(f"  {f['feature']:<24} {f[key]:.3f}{'  FLAG' if f['flag'] else ''}")
    if "identifies_group" in r:
        print(f"identifies {a.group}:")
        for f in r["identifies_group"]:
            note = "constant within" if f["constant_within_group"] else "varies within"
            print(f"  {f['feature']:<24} {note}, {f['distinct_over_groups']} distinct"
                  f"{'  FLAG' if f['flag'] else ''}")
    print(f"permuted target: {key} {r['permuted'][key]:.3f}")
    d = r["duplicates"]
    print(f"test rows with an identical training row: {d['test_rows_with_a_train_twin']}"
          f" of {d['test_rows']}")


if __name__ == "__main__":
    main()

"""Explore positive sample weights for B_env on the existing 2023 -> 2024 B1 split.

Run from the repository root with the existing B1 artifact directory:
    uvx --with numpy --with scipy --with scikit-learn python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/weight_sweep_b1.py ART_DIR \
      projects/_bear/akita-bear-risk-grid-100m/outputs/b1_positive_weight_sweep.json

This does not change model_eval.py or use 2025/2026 labels. The existing
unweighted fit must reproduce its capture@5% before any weighted fit. Explicit
all-one weights are also measured: scikit-learn 1.9.1 gives a different B1
ranking when sample_weight is passed, even if every weight equals one.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import model_eval as me

WEIGHTS = (1, 3, 10, 30)
BASELINE_CAPTURE = 0.5341823056300268
INPUTS = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz", "reports_by_year.npz", "grid_mask.npz")
METRICS = ("capture@1%", "capture@5%", "capture@10%", "auc", "ap")


def sample_weights(y, positive_weight):
    y = np.asarray(y, dtype=bool)
    if y.ndim != 1 or positive_weight <= 0:
        raise ValueError("labels must be one-dimensional and positive weight must be > 0")
    weights = np.ones(len(y), dtype=np.float64)
    weights[y] = positive_weight
    return weights, {"positive": float(weights[y].sum()), "negative": float(weights[~y].sum())}


def fit_predict(Xtr, ytr, Xte, positive_weight):
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(**me.HGB, random_state=0)
    if positive_weight is None:
        _, totals = sample_weights(ytr, 1)
        model.fit(Xtr, ytr)
    else:
        weights, totals = sample_weights(ytr, positive_weight)
        model.fit(Xtr, ytr, sample_weight=weights)
    return model.predict_proba(Xte)[:, 1], totals


def run_sweep(Xtr, ytr, Xte, yte, counts=None, expected_baseline=BASELINE_CAPTURE, fit=fit_predict):
    if counts is None:
        counts = yte.astype(float)
    rows = []
    for positive_weight in (None, *WEIGHTS):
        scores, totals = fit(Xtr, ytr, Xte, positive_weight)
        evaluated = me.evaluate({"B_env": scores}, yte, counts, np.empty(0), [], B=0, seed=0)["B_env"]
        row = {"setting": "existing_unweighted" if positive_weight is None else "explicit_sample_weight",
               "positive_weight": positive_weight or 1, "negative_weight": 1,
               "sample_weight_passed": positive_weight is not None,
               "train_weight_total": totals, **{key: evaluated[key] for key in METRICS}}
        if positive_weight is None and abs(row["capture@5%"] - expected_baseline) > 0.0005:
            raise ValueError(f"baseline capture@5% did not reproduce: {row['capture@5%']:.9f}"
                             f" vs {expected_baseline:.9f}; candidates were not run")
        print(f"setting={row['setting']} positive_weight={row['positive_weight']}"
              f" capture@5%={row['capture@5%']:.9f}"
              + (" baseline reproduced" if positive_weight is None else ""), flush=True)
        rows.append(row)
    return rows


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    import sklearn

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path, help="existing B1 artifact directory")
    ap.add_argument("out", type=Path, help="small JSON result path")
    args = ap.parse_args()
    source_hashes = {name: sha256(args.art / name) for name in INPUTS}
    static, all_counts, muni = me.load(args.art)
    counts = {year: all_counts[year] for year in (2023, 2024)}
    Xtr, names, ytr, _ = me.design(static, counts, muni, 2023, history=False)
    Xte, test_names, yte, test_counts = me.design(static, counts, muni, 2024, history=False)
    if names != test_names or len(ytr) != 1168211 or int(ytr.sum()) != 3439 or int(yte.sum()) != 1492:
        raise ValueError("B1 columns, cell count, or positive counts differ from the existing experiment")
    rows = run_sweep(Xtr, ytr, Xte, yte, test_counts)
    baseline = rows[0]["capture@5%"]
    weighted_one = rows[1]["capture@5%"]
    improved = [r for r in rows[2:] if r["capture@5%"] > baseline]
    result = {
        "mode": "exploratory",
        "question": "Does changing only the positive-cell sample weight improve B_env capture@5% in B1?",
        "setup": {"train_year": 2023, "test_year": 2024, "model": "B_env",
                  "positive_weights": list(WEIGHTS), "negative_weight": 1, "seed": 0,
                  "existing_baseline_has_no_sample_weight": True,
                  "hgb": me.HGB, "feature_names": names, "n_train": len(ytr),
                  "n_train_positive": int(ytr.sum()), "n_test": len(yte),
                  "n_test_positive": int(yte.sum()), "numpy": np.__version__,
                  "sklearn": sklearn.__version__, "input_sha256": source_hashes,
                  "baseline_reference_capture@5%": BASELINE_CAPTURE,
                  "baseline_check_tolerance": 0.0005},
        "results": rows,
        "decision": {"improved_weights_vs_existing_baseline": [r["positive_weight"] for r in improved],
                     "best_improvement_vs_existing_baseline": max(
                         (r["capture@5%"] - baseline for r in improved), default=0.0),
                     "weighted_one_capture@5%": weighted_one,
                     "improved_weights_vs_explicit_weight_one": [
                         r["positive_weight"] for r in rows[2:] if r["capture@5%"] > weighted_one],
                     "sample_weighting_alone_improved_b1": bool(improved)},
        "limitations": "B1 exploratory only; no 2025/2026 evaluation, uncertainty interval, or probability calibration claim",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"results": rows, "decision": result["decision"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

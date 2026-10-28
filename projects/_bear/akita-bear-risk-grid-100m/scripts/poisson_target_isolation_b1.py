"""Isolate 2023 binary-vs-count targets in the same Poisson HGB on B1.

Run from the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy --with scikit-learn python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/poisson_target_isolation_b1.py ART_DIR \
      projects/_bear/akita-bear-risk-grid-100m/outputs/b1_poisson_target_isolation.json

Uses only 2023/2024 labels. Reproduces existing classifier and count-Poisson
scores before fitting binary-Poisson. Both Poisson models call the identical
fit function with the same features, rows, HGB parameters, and no weights.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import count_target_b1 as prior
import model_eval as me

CLASSIFIER_CAPTURE = prior.BASELINE_CAPTURE
COUNT_CAPTURE = 0.5475871313672922
TOLERANCE = 1e-9


def measure(scores, y, counts):
    evaluated = me.evaluate({"B_env": scores}, y, counts, np.empty(0), [], B=0, seed=0)["B_env"]
    return {key: evaluated[key] for key in prior.METRICS}


def decide(rows):
    by_name = {row["setting"]: row for row in rows}
    classifier = by_name["B_env_classifier"]["capture@5%"]
    binary = by_name["binary_poisson"]["capture@5%"]
    count = by_name["count_poisson"]["capture@5%"]
    difference = count - binary
    return {"count_minus_binary_capture@5%": difference,
            "count_minus_classifier_capture@5%": count - classifier,
            "binary_minus_classifier_capture@5%": binary - classifier,
            "count_has_additional_signal_within_poisson": bool(difference > 0)}


def run_experiment(Xtr, ytr, train_counts, Xte, yte, test_counts, *,
                   expected_classifier=CLASSIFIER_CAPTURE, expected_count=COUNT_CAPTURE,
                   fit_cls=prior.fit_classifier, fit_poisson=prior.fit_poisson):
    target_summary = prior.validate_targets(ytr, train_counts)
    classifier = fit_cls(Xtr, ytr)
    classifier_metrics = measure(classifier.predict_proba(Xte)[:, 1], yte, test_counts)
    if abs(classifier_metrics["capture@5%"] - expected_classifier) > TOLERANCE:
        raise ValueError("classifier baseline capture@5% did not reproduce; Poisson models were not run")
    print(f"B_env_classifier capture@5%={classifier_metrics['capture@5%']:.12f} reproduced", flush=True)

    # Reproduce the prior run with the original count target before isolating
    # the only new variant. Both calls below use the exact same fit function.
    count_model = fit_poisson(Xtr, train_counts)
    count_metrics = measure(count_model.predict(Xte), yte, test_counts)
    if abs(count_metrics["capture@5%"] - expected_count) > TOLERANCE:
        raise ValueError("count_poisson reproduction failed; binary_poisson was not run")
    print(f"count_poisson capture@5%={count_metrics['capture@5%']:.12f} reproduced", flush=True)

    binary_target = ytr.astype(float)
    binary_model = fit_poisson(Xtr, binary_target)
    binary_metrics = measure(binary_model.predict(Xte), yte, test_counts)
    print(f"binary_poisson capture@5%={binary_metrics['capture@5%']:.12f}", flush=True)
    rows = [
        {"setting": "B_env_classifier", "model": "HistGradientBoostingClassifier",
         "target": "2023 binary presence", **classifier_metrics},
        {"setting": "binary_poisson", "model": "HistGradientBoostingRegressor",
         "loss": "poisson", "target": "2023 binary presence", **binary_metrics},
        {"setting": "count_poisson", "model": "HistGradientBoostingRegressor",
         "loss": "poisson", "target": "2023 report count", **count_metrics},
    ]
    return rows, target_summary


def main():
    import sklearn

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path, help="existing B1 artifact directory")
    ap.add_argument("out", type=Path, help="small JSON result path")
    args = ap.parse_args()
    source_hashes = {name: prior.sha256(args.art / name) for name in prior.INPUTS}
    static, counts, muni = prior.load_b1(args.art)
    Xtr, names, ytr, train_counts = me.design(static, counts, muni, 2023, history=False)
    Xte, test_names, yte, test_counts = me.design(static, counts, muni, 2024, history=False)
    if names != test_names or len(ytr) != 1_168_211 or int(ytr.sum()) != 3_439 \
            or len(yte) != 1_168_211 or int(yte.sum()) != 1_492:
        raise ValueError("B1 columns, cell count, or positive counts differ from the existing experiment")
    if prior.validate_targets(ytr, train_counts)["n_reports"] != 3_895:
        raise ValueError("2023 training report total differs from the existing B1 experiment")
    rows, target_summary = run_experiment(Xtr, ytr, train_counts, Xte, yte, test_counts)
    decision = decide(rows)
    result = {
        "mode": "exploratory",
        "question": "Within the same Poisson HGB, does the 2023 count target improve 2024 binary-cell ranking over the binary target?",
        "setup": {"train_year": 2023, "test_year": 2024, "features": "B_env static only",
                  "poisson_model": "HistGradientBoostingRegressor", "loss": "poisson",
                  "hgb": me.HGB, "seed": 0, "sample_weight_passed": False,
                  "feature_names": names, "n_train": int(len(ytr)),
                  "n_test": int(len(yte)), "n_test_positive": int(yte.sum()),
                  "numpy": np.__version__, "sklearn": sklearn.__version__,
                  "input_sha256": source_hashes,
                  "classifier_reference_capture@5%": CLASSIFIER_CAPTURE,
                  "count_reference_capture@5%": COUNT_CAPTURE,
                  "reproduction_tolerance": TOLERANCE},
        "train_target_summary": target_summary,
        "results": rows,
        "decision": decision,
        "limitations": "B1 exploratory point estimate only; no uncertainty interval or 2025/2026 evaluation."
                       " Report counts also reflect reporting opportunity. The classifier is a reference,"
                       " while count-vs-binary within Poisson isolates the target definition.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Explore count-target Poisson HGB against the B_env classifier on B1 only.

Run from the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy --with scikit-learn python \
      projects/akita-bear-risk-grid-100m/scripts/count_target_b1.py ART_DIR \
      projects/akita-bear-risk-grid-100m/outputs/b1_count_target_poisson.json

Only 2023/2024 count arrays are loaded. No weighting, mining, soft labels, or
additional model settings are used. The 2024 evaluation target remains binary.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import model_eval as me

BASELINE_CAPTURE = 0.5341823056300268
METRICS = ("capture@1%", "capture@5%", "capture@10%", "auc", "ap")
INPUTS = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
          "reports_by_year.npz", "grid_mask.npz")


def load_b1(art):
    """Reuse model_eval's static feature builder, loading only B1 count arrays."""
    with np.load(art / "worldcover.npz") as wc, np.load(art / "dem.npz") as dem, \
            np.load(art / "worldpop.npz") as pop, np.load(art / "osm.npz") as osm:
        static = me.ft.static_features(wc, dem, pop, osm)
    with np.load(art / "reports_by_year.npz") as reports:
        counts = {year: reports[f"c{year}"].astype(float) for year in (2023, 2024)}
    with np.load(art / "grid_mask.npz") as grid:
        muni = grid["muni"]
    return static, counts, muni


def validate_targets(y, counts):
    """Reject invalid/misaligned report counts rather than silently binarizing."""
    y = np.asarray(y, dtype=bool)
    counts = np.asarray(counts)
    if y.ndim != 1 or counts.shape != y.shape or not np.isfinite(counts).all() \
            or np.any(counts < 0) or np.any(counts != np.floor(counts)) \
            or not np.array_equal(y, counts > 0) or not y.any():
        raise ValueError("count target must be aligned non-negative integer report counts with positive cells")
    return {"n_positive_cells": int(y.sum()), "n_reports": int(counts.sum()),
            "n_cells_with_multiple_reports": int(np.count_nonzero(counts > 1)),
            "max_reports_in_cell": int(counts.max())}


def fit_classifier(X, y):
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(**me.HGB, random_state=0)
    model.fit(X, y)  # Deliberately no sample_weight.
    return model


def fit_poisson(X, counts):
    from sklearn.ensemble import HistGradientBoostingRegressor

    model = HistGradientBoostingRegressor(**me.HGB, loss="poisson", random_state=0)
    model.fit(X, counts)  # Deliberately no sample_weight.
    return model


def _metrics(scores, y, counts):
    evaluated = me.evaluate({"B_env": scores}, y, counts, np.empty(0), [], B=0, seed=0)["B_env"]
    return {key: evaluated[key] for key in METRICS}


def run_experiment(Xtr, ytr, train_counts, Xte, yte, test_counts, *,
                   expected_baseline=BASELINE_CAPTURE, fit_cls=fit_classifier,
                   fit_count=fit_poisson):
    target_summary = validate_targets(ytr, train_counts)
    classifier = fit_cls(Xtr, ytr)
    baseline_metrics = _metrics(classifier.predict_proba(Xte)[:, 1], yte, test_counts)
    baseline = baseline_metrics["capture@5%"]
    if abs(baseline - expected_baseline) > 1e-9:
        raise ValueError(f"baseline capture@5% did not reproduce: {baseline:.12f}"
                         f" vs {expected_baseline:.12f}; Poisson model was not run")
    print(f"B_env_classifier capture@5%={baseline:.12f} reproduced", flush=True)
    rows = [{"setting": "B_env_classifier", "target": "2023 binary presence",
             "model": "HistGradientBoostingClassifier", "delta_capture@5%": 0.0,
             **baseline_metrics}]
    poisson = fit_count(Xtr, train_counts)
    poisson_metrics = _metrics(poisson.predict(Xte), yte, test_counts)
    rows.append({"setting": "count_poisson", "target": "2023 report count",
                 "model": "HistGradientBoostingRegressor", "loss": "poisson",
                 "delta_capture@5%": poisson_metrics["capture@5%"] - baseline,
                 **poisson_metrics})
    print(f"count_poisson capture@5%={rows[1]['capture@5%']:.12f}"
          f" delta={rows[1]['delta_capture@5%']:+.12f}", flush=True)
    return rows, target_summary


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
    static, counts, muni = load_b1(args.art)
    Xtr, names, ytr, train_counts = me.design(static, counts, muni, 2023, history=False)
    Xte, test_names, yte, test_counts = me.design(static, counts, muni, 2024, history=False)
    if names != test_names or len(ytr) != 1_168_211 or int(ytr.sum()) != 3_439 \
            or len(yte) != 1_168_211 or int(yte.sum()) != 1_492:
        raise ValueError("B1 columns, cell count, or positive counts differ from the existing experiment")
    if validate_targets(ytr, train_counts)["n_reports"] != 3_895:
        raise ValueError("2023 training report total differs from the existing B1 experiment")
    rows, target_summary = run_experiment(Xtr, ytr, train_counts, Xte, yte, test_counts)
    result = {
        "mode": "exploratory",
        "question": "Does a 2023 count-target Poisson HGB improve 2024 binary-cell ranking over B_env?",
        "setup": {"train_year": 2023, "test_year": 2024, "features": "B_env static only",
                  "hgb": me.HGB, "poisson_loss": "poisson", "seed": 0,
                  "sample_weight_passed": False, "feature_names": names,
                  "n_train": int(len(ytr)), "n_test": int(len(yte)),
                  "n_test_positive": int(yte.sum()), "numpy": np.__version__,
                  "sklearn": sklearn.__version__, "input_sha256": source_hashes,
                  "baseline_reference_capture@5%": BASELINE_CAPTURE,
                  "baseline_check_tolerance": 1e-9},
        "train_target_summary": target_summary,
        "results": rows,
        "decision": {"improved_vs_classifier_capture@5%": rows[1]["delta_capture@5%"] > 0},
        "limitations": "B1 exploration only. Count target also changes classifier to Poisson regressor/loss;"
                       " the difference is not a pure target-only effect. Counts reflect reporting as well"
                       " as repeated bear events. No 2025/2026 evaluation or uncertainty interval.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

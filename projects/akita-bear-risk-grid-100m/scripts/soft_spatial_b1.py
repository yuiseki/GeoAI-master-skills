"""Test fixed soft spatial labels on B1 (2023 train -> 2024 binary evaluation).

Usage from the repository root:
    uvx --with numpy --with scipy --with scikit-learn python \
      projects/akita-bear-risk-grid-100m/scripts/soft_spatial_b1.py ART_DIR \
      projects/akita-bear-risk-grid-100m/outputs/b1_soft_spatial_label.json

HistGradientBoostingClassifier does not accept fractional labels. Soft targets
therefore use HistGradientBoostingRegressor with the same HGB parameters and no
sample_weight. A hard-label regressor control isolates the label change; the
existing classifier baseline remains a separate operational comparator.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

import model_eval as me

BASELINE_CAPTURE = 0.5341823056300268
RADII = (("S100", 100), ("S200", 200), ("S300", 300))
METRICS = ("capture@1%", "capture@5%", "capture@10%", "auc", "ap")
INPUTS = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
          "reports_by_year.npz", "grid_mask.npz")


def load_b1(art):
    """Reuse the existing static-feature builder; load only 2023/2024 labels."""
    with np.load(art / "worldcover.npz") as wc, np.load(art / "dem.npz") as dem, \
            np.load(art / "worldpop.npz") as pop, np.load(art / "osm.npz") as osm:
        static = me.ft.static_features(wc, dem, pop, osm)
    with np.load(art / "reports_by_year.npz") as reports:
        counts = {year: reports[f"c{year}"].astype(float) for year in (2023, 2024)}
    with np.load(art / "grid_mask.npz") as grid:
        muni = grid["muni"]
    return static, counts, muni


def make_targets(positive_grid, inside_grid, radius):
    """Soft 2023 training targets in model_eval.design's row-major inside order."""
    positive_grid = np.asarray(positive_grid, dtype=bool)
    inside_grid = np.asarray(inside_grid, dtype=bool)
    if positive_grid.shape != inside_grid.shape or positive_grid.ndim != 2:
        raise ValueError("positive and inside grids must have the same 2D shape")
    if radius not in (100, 200, 300):
        raise ValueError("only the preregistered 100, 200, and 300 m radii are allowed")
    positive_grid = positive_grid & inside_grid
    if not positive_grid.any():
        raise ValueError("no positive training cells")
    distance = distance_transform_edt(~positive_grid, sampling=100.0)
    targets = np.zeros(positive_grid.shape, dtype=np.float32)
    targets[positive_grid] = 1.0
    targets[(distance > 0) & (distance <= 100)] = 0.5
    if radius >= 200:
        targets[(distance > 100) & (distance <= 200)] = 0.25
    if radius >= 300:
        targets[(distance > 200) & (distance <= 300)] = 0.125
    return targets[inside_grid]


def fit_classifier(X, y):
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(**me.HGB, random_state=0)
    model.fit(X, y)  # No sample_weight.
    return model


def fit_regressor(X, y):
    from sklearn.ensemble import HistGradientBoostingRegressor

    model = HistGradientBoostingRegressor(**me.HGB, random_state=0)
    model.fit(X, y)  # No sample_weight; default loss is squared_error.
    return model


def _metrics(scores, y, counts):
    evaluated = me.evaluate({"B_env": scores}, y, counts, np.empty(0), [], B=0, seed=0)["B_env"]
    return {key: evaluated[key] for key in METRICS}


def _target_counts(targets):
    return {str(value): int(np.count_nonzero(targets == value))
            for value in (1.0, 0.5, 0.25, 0.125) if np.any(targets == value)}


def run_experiment(Xtr, ytr, Xte, yte, test_counts, positive_grid, inside_grid, *,
                   expected_baseline=BASELINE_CAPTURE, fit_cls=fit_classifier,
                   fit_reg=fit_regressor):
    """Check classifier baseline, then compare hard and three soft regression targets."""
    classifier = fit_cls(Xtr, ytr)
    cls_metrics = _metrics(classifier.predict_proba(Xte)[:, 1], yte, test_counts)
    cls_capture = cls_metrics["capture@5%"]
    if abs(cls_capture - expected_baseline) > 1e-9:
        raise ValueError(f"baseline capture@5% did not reproduce: {cls_capture:.12f}"
                         f" vs {expected_baseline:.12f}; other models were not run")
    print(f"B_env_classifier capture@5%={cls_capture:.12f} reproduced", flush=True)
    rows = [{"setting": "B_env_classifier", "model": "HistGradientBoostingClassifier",
             "target": "hard 0/1", "delta_vs_classifier_capture@5%": 0.0, **cls_metrics}]

    hard_targets = ytr.astype(np.float32)
    regressor = fit_reg(Xtr, hard_targets)
    hard_metrics = _metrics(regressor.predict(Xte), yte, test_counts)
    hard_capture = hard_metrics["capture@5%"]
    rows.append({"setting": "hard_regressor", "model": "HistGradientBoostingRegressor",
                 "target": "hard 0/1", "target_counts": _target_counts(hard_targets),
                 "delta_vs_classifier_capture@5%": hard_capture - cls_capture,
                 "delta_vs_hard_regressor_capture@5%": 0.0, **hard_metrics})
    print(f"hard_regressor capture@5%={hard_capture:.12f}", flush=True)

    for setting, radius in RADII:
        targets = make_targets(positive_grid, inside_grid, radius)
        if len(targets) != len(ytr) or not np.array_equal(targets == 1.0, ytr):
            raise ValueError("soft targets do not align with the 2023 training labels")
        model = fit_reg(Xtr, targets)
        evaluated = _metrics(model.predict(Xte), yte, test_counts)
        row = {"setting": setting, "model": "HistGradientBoostingRegressor",
               "radius_m": radius, "target_counts": _target_counts(targets),
               "delta_vs_classifier_capture@5%": evaluated["capture@5%"] - cls_capture,
               "delta_vs_hard_regressor_capture@5%": evaluated["capture@5%"] - hard_capture,
               **evaluated}
        rows.append(row)
        print(f"{setting} capture@5%={row['capture@5%']:.12f}"
              f" delta_vs_hard_regressor={row['delta_vs_hard_regressor_capture@5%']:+.12f}"
              f" delta_vs_classifier={row['delta_vs_classifier_capture@5%']:+.12f}", flush=True)
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
    static, counts, muni = load_b1(args.art)
    Xtr, names, ytr, _ = me.design(static, counts, muni, 2023, history=False)
    Xte, test_names, yte, test_counts = me.design(static, counts, muni, 2024, history=False)
    inside = muni >= 0
    positive_grid = (counts[2023] > 0) & inside
    if names != test_names or len(ytr) != 1_168_211 or int(ytr.sum()) != 3_439 \
            or len(yte) != 1_168_211 or int(yte.sum()) != 1_492 \
            or not np.array_equal(positive_grid[inside], ytr):
        raise ValueError("B1 columns, cell count, or 2023/2024 labels differ from the existing experiment")
    rows = run_experiment(Xtr, ytr, Xte, yte, test_counts, positive_grid, inside)
    best = max(rows[2:], key=lambda row: row["delta_vs_hard_regressor_capture@5%"])
    result = {
        "mode": "exploratory",
        "question": "Does a soft 2023 spatial training label improve B1 ranking over a hard-label HGB regressor?",
        "setup": {"train_year": 2023, "test_year": 2024, "model_features": "B_env static only",
                  "soft_model": "HistGradientBoostingRegressor", "soft_loss": "squared_error",
                  "controls": ["existing B_env HistGradientBoostingClassifier",
                               "hard-label HistGradientBoostingRegressor"],
                  "settings": [{"name": name, "radius_m": radius} for name, radius in RADII],
                  "distance": "Euclidean cell-center distance to nearest 2023 positive; 100 m grid",
                  "target_values": {"positive_cell": 1.0, "(0,100]m": 0.5,
                                    "(100,200]m": 0.25, "(200,300]m": 0.125,
                                    "other": 0.0},
                  "test_target": "original binary 2024 cell label",
                  "sample_weight_passed": False, "hgb": me.HGB, "seed": 0,
                  "feature_names": names, "n_train": int(len(ytr)),
                  "n_train_positive": int(ytr.sum()), "n_test": int(len(yte)),
                  "n_test_positive": int(yte.sum()), "numpy": np.__version__,
                  "sklearn": sklearn.__version__, "input_sha256": source_hashes,
                  "baseline_reference_capture@5%": BASELINE_CAPTURE,
                  "baseline_check_tolerance": 1e-9},
        "results": rows,
        "decision": {"improved_vs_hard_regressor": [r["setting"] for r in rows[2:]
                                                  if r["delta_vs_hard_regressor_capture@5%"] > 0],
                     "improved_vs_existing_classifier": [r["setting"] for r in rows[2:]
                                                         if r["delta_vs_classifier_capture@5%"] > 0],
                     "best_setting_vs_hard_regressor": best["setting"] if
                     best["delta_vs_hard_regressor_capture@5%"] > 0 else None,
                     "soft_label_improved_within_regressor":
                     best["delta_vs_hard_regressor_capture@5%"] > 0},
        "limitations": "The soft-label model is a regressor, not the original classifier;"
                       " compare soft vs hard targets within that same regressor to isolate the label."
                       " B1 only; no uncertainty interval or 2025/2026 evaluation.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Compare binary and count targets with the existing squared-error HGB on B1.

Run from the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy --with scikit-learn python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/squared_target_isolation_b1.py ART_DIR \
      projects/_bear/akita-bear-risk-grid-100m/outputs/b1_squared_target_isolation.json

Only 2023/2024 labels are loaded. The two Poisson rows come from prior B1 JSON
after checking input hashes, feature names, HGB settings, years, and versions.
No Poisson, classifier, or other setting is refit in this exploration.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import count_target_b1 as prior
import model_eval as me
import soft_spatial_b1 as soft

TOLERANCE = 1e-9
PROJECT = Path(__file__).resolve().parents[1]
SOFT_REFERENCE = PROJECT / "outputs/b1_soft_spatial_label.json"
POISSON_REFERENCE = PROJECT / "outputs/b1_poisson_target_isolation.json"


def fit_squared(X, target):
    """Call exactly the already-used hard-target HGB squared-error fit."""
    return soft.fit_regressor(X, target)


def measure(scores, y, counts):
    evaluated = me.evaluate({"B_env": scores}, y, counts, np.empty(0), [], B=0, seed=0)["B_env"]
    return {key: evaluated[key] for key in prior.METRICS}


def validate_references(soft_result, poisson_result, input_hashes, feature_names, sklearn_version):
    """Do not mix prior metrics from another artifact, feature set, or HGB fit."""
    for label, result, loss in (("squared", soft_result, "squared_error"),
                                ("poisson", poisson_result, "poisson")):
        setup = result.get("setup", {})
        actual_loss = setup.get("soft_loss") if label == "squared" else setup.get("loss")
        if (setup.get("train_year"), setup.get("test_year")) != (2023, 2024) \
                or setup.get("input_sha256") != input_hashes \
                or setup.get("feature_names") != feature_names \
                or setup.get("hgb") != me.HGB \
                or setup.get("sklearn") != sklearn_version \
                or setup.get("sample_weight_passed") is not False \
                or actual_loss != loss:
            raise ValueError(f"reference provenance mismatch for {label} result")
    squared_rows = {row["setting"]: row for row in soft_result.get("results", [])}
    poisson_rows = {row["setting"]: row for row in poisson_result.get("results", [])}
    try:
        squared_binary = squared_rows["hard_regressor"]
        references = [poisson_rows[name] for name in ("binary_poisson", "count_poisson")]
        for row in (squared_binary, *references):
            for key in prior.METRICS:
                float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("reference provenance lacks required B1 model metrics") from exc
    return [{"setting": row["setting"], "provenance": "prior_B1_result",
             **{key: float(row[key]) for key in prior.METRICS}} for row in references]


def run_experiment(Xtr, ytr, train_counts, Xte, yte, test_counts, *,
                   expected_binary, fit=fit_squared):
    target_summary = prior.validate_targets(ytr, train_counts)
    binary_target = ytr.astype(np.float32)
    count_target = train_counts.astype(np.float32)
    if not np.array_equal(count_target.astype(float), train_counts):
        raise ValueError("report counts are not represented exactly in float32")
    binary_model = fit(Xtr, binary_target)
    binary_metrics = measure(binary_model.predict(Xte), yte, test_counts)
    if abs(binary_metrics["capture@5%"] - expected_binary) > TOLERANCE:
        raise ValueError("binary_squared reproduction failed; count_squared was not run")
    print(f"binary_squared capture@5%={binary_metrics['capture@5%']:.12f} reproduced", flush=True)
    count_model = fit(Xtr, count_target)
    count_metrics = measure(count_model.predict(Xte), yte, test_counts)
    print(f"count_squared capture@5%={count_metrics['capture@5%']:.12f}", flush=True)
    return ([{"setting": "binary_squared", "model": "HistGradientBoostingRegressor",
              "loss": "squared_error", "target": "2023 binary presence",
              "provenance": "rerun_B1", **binary_metrics},
             {"setting": "count_squared", "model": "HistGradientBoostingRegressor",
              "loss": "squared_error", "target": "2023 report count",
              "provenance": "rerun_B1", **count_metrics}], target_summary)


def decide(rows):
    by_name = {row["setting"]: row for row in rows}
    squared_diff = by_name["count_squared"]["capture@5%"] - by_name["binary_squared"]["capture@5%"]
    poisson_diff = by_name["count_poisson"]["capture@5%"] - by_name["binary_poisson"]["capture@5%"]
    return {"count_minus_binary_squared_capture@5%": squared_diff,
            "count_minus_binary_poisson_capture@5%": poisson_diff,
            "count_signal_not_limited_to_poisson": bool(squared_diff > 0)}


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
    soft_result = json.loads(SOFT_REFERENCE.read_text(encoding="utf-8"))
    poisson_result = json.loads(POISSON_REFERENCE.read_text(encoding="utf-8"))
    poisson_rows = validate_references(soft_result, poisson_result, source_hashes, names, sklearn.__version__)
    squared_reference = next(row for row in soft_result["results"] if row["setting"] == "hard_regressor")
    squared_rows, target_summary = run_experiment(
        Xtr, ytr, train_counts, Xte, yte, test_counts,
        expected_binary=squared_reference["capture@5%"])
    for key in prior.METRICS:
        if abs(squared_rows[0][key] - squared_reference[key]) > TOLERANCE:
            raise ValueError(f"binary_squared {key} differs from the prior hard_regressor result")
    rows = squared_rows + poisson_rows
    decision = decide(rows)
    result = {
        "mode": "exploratory",
        "question": "Does the 2023 count target improve B1 ranking within squared-error HGB, not just Poisson HGB?",
        "setup": {"train_year": 2023, "test_year": 2024, "features": "B_env static only",
                  "squared_model": "HistGradientBoostingRegressor", "loss": "squared_error",
                  "hgb": me.HGB, "seed": 0, "sample_weight_passed": False,
                  "training_target_dtype": "float32", "feature_names": names,
                  "n_train": int(len(ytr)), "n_test": int(len(yte)),
                  "n_test_positive": int(yte.sum()), "numpy": np.__version__,
                  "sklearn": sklearn.__version__, "input_sha256": source_hashes,
                  "binary_squared_reference_capture@5%": squared_reference["capture@5%"],
                  "reference_result_paths": [str(SOFT_REFERENCE.relative_to(PROJECT)),
                                             str(POISSON_REFERENCE.relative_to(PROJECT))],
                  "reproduction_tolerance": TOLERANCE},
        "train_target_summary": target_summary,
        "results": rows,
        "decision": decision,
        "limitations": "B1 exploratory point estimate only; no uncertainty interval or 2025/2026 evaluation."
                       " Poisson rows are referenced from prior B1 JSON, not refit."
                       " Report counts also reflect reporting opportunity.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

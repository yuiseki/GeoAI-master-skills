"""Fixed B1-selected Poisson target comparison on B2 and B3; no tuning.

Run from repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy --with scikit-learn python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/poisson_robustness_b2_b3.py ART_DIR OUT_JSON
"""

import argparse
import json
from pathlib import Path

import numpy as np

import count_target_b1 as prior
import model_eval as me

METRICS = prior.METRICS
SPLITS = (("B2", (2023, 2024), 2025), ("B3", (2023, 2024, 2025), 2026))
REFERENCE_NAMES = {
    "B2": "b2_confirm_2023-2024_to_2025.json",
    "B3": "b3_confirm_2023-2025_to_2026.json",
}
TOLERANCE = 1e-9


def load_inputs(art):
    """Load static features once and exactly the four required label years."""
    with np.load(art / "worldcover.npz") as wc, np.load(art / "dem.npz") as dem, \
            np.load(art / "worldpop.npz") as pop, np.load(art / "osm.npz") as osm:
        static = me.ft.static_features(wc, dem, pop, osm)
    with np.load(art / "reports_by_year.npz") as reports:
        counts = {year: reports[f"c{year}"].astype(float) for year in range(2023, 2027)}
    with np.load(art / "grid_mask.npz") as grid:
        muni = grid["muni"]
    inside = muni >= 0
    names = list(static)
    X = np.column_stack([static[n][inside] for n in names]).astype(np.float32)
    counts = {year: count[inside] for year, count in counts.items()}
    return X, names, counts


def run_split(X, counts, train_years, test_year, *, expected_classifier,
              fit_cls=prior.fit_classifier, fit_poisson=prior.fit_poisson):
    """Fit three fixed models from scratch and score binary test cells."""
    if not train_years or max(train_years) >= test_year or len(set(train_years)) != len(train_years):
        raise ValueError("training years must be unique and precede test year")
    if any(len(counts[year]) != len(X) for year in (*train_years, test_year)):
        raise ValueError("label and feature rows are misaligned")
    Xtr = np.vstack([X for _ in train_years])
    ctr = np.concatenate([counts[year] for year in train_years])
    ytr = ctr > 0
    summary = prior.validate_targets(ytr, ctr)
    cte = counts[test_year]
    yte = cte > 0
    prior.validate_targets(yte, cte)

    classifier = fit_cls(Xtr, ytr)
    base = prior._metrics(classifier.predict_proba(X)[:, 1], yte, cte)
    if expected_classifier is not None and abs(base["capture@5%"] - expected_classifier) > TOLERANCE:
        raise ValueError(f"classifier baseline did not reproduce: {base['capture@5%']:.12f}"
                         f" vs {expected_classifier:.12f}; Poisson models not run")
    print(f"{train_years} -> {test_year}: B_env_classifier capture@5%={base['capture@5%']:.12f}", flush=True)

    binary = fit_poisson(Xtr, ytr.astype(float))
    binary_metrics = prior._metrics(binary.predict(X), yte, cte)
    print(f"{train_years} -> {test_year}: binary_poisson capture@5%={binary_metrics['capture@5%']:.12f}", flush=True)
    count = fit_poisson(Xtr, ctr)
    count_metrics = prior._metrics(count.predict(X), yte, cte)
    print(f"{train_years} -> {test_year}: count_poisson capture@5%={count_metrics['capture@5%']:.12f}", flush=True)
    rows = [
        {"setting": "B_env_classifier", "model": "HistGradientBoostingClassifier", "target": "binary presence", **base},
        {"setting": "binary_poisson", "model": "HistGradientBoostingRegressor", "loss": "poisson",
         "target": "binary presence", **binary_metrics},
        {"setting": "count_poisson", "model": "HistGradientBoostingRegressor", "loss": "poisson",
         "target": "report count", **count_metrics},
    ]
    meta = {"train_years": list(train_years), "test_year": test_year,
            "n_train": int(len(ctr)), "n_test": int(len(cte)),
            "n_test_positive": int(yte.sum()), "train_target_summary": summary}
    return rows, meta


def decide(differences):
    a, b = differences["B2"], differences["B3"]
    if a > 0 and b > 0:
        verdict = "robust_same_direction"
    elif a <= 0 and b <= 0:
        verdict = "reversed_or_flat"
    else:
        verdict = "mixed_not_robust"
    return {"verdict": verdict, "B2_count_minus_binary_capture@5%": a,
            "B3_count_minus_binary_capture@5%": b}


def _by_setting(rows):
    return {row["setting"]: row for row in rows}


def main():
    import sklearn

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    source_hashes = {name: prior.sha256(args.art / name) for name in prior.INPUTS}
    b1_path = Path(__file__).resolve().parents[1] / "outputs/b1_poisson_target_isolation.json"
    b1 = json.loads(b1_path.read_text(encoding="utf-8"))
    X, names, counts = load_inputs(args.art)
    if b1["setup"]["input_sha256"] != source_hashes or b1["setup"]["feature_names"] != names \
            or b1["setup"]["hgb"] != me.HGB or b1["setup"]["sklearn"] != sklearn.__version__ \
            or b1["setup"]["train_year"] != 2023 or b1["setup"]["test_year"] != 2024 \
            or b1["setup"]["sample_weight_passed"] or len(X) != 1_168_211:
        raise ValueError("B1 provenance or B_env feature contract changed; abort")
    expected_positive = {2023: 3439, 2024: 1492, 2025: 10729, 2026: 3036}
    if {year: int(np.count_nonzero(c > 0)) for year, c in counts.items()} != expected_positive:
        raise ValueError("yearly positive counts differ from existing label artifact")
    if set(_by_setting(b1["results"])) != {"B_env_classifier", "binary_poisson", "count_poisson"}:
        raise ValueError("B1 reference model set differs")

    outputs, differences = {}, {}
    for block, train_years, test_year in SPLITS:
        ref_path = args.art / "eval" / REFERENCE_NAMES[block]
        reference = json.loads(ref_path.read_text(encoding="utf-8"))
        setup = reference["setup"]
        if setup["train"] != list(train_years) or setup["test"] != test_year \
                or setup["hgb"] != me.HGB or setup["seed"] != 0:
            raise ValueError(f"{block} classifier reference setup differs")
        rows, meta = run_split(X, counts, train_years, test_year,
                               expected_classifier=reference["B_env"]["capture@5%"])
        by = _by_setting(rows)
        delta = by["count_poisson"]["capture@5%"] - by["binary_poisson"]["capture@5%"]
        differences[block] = delta
        outputs[block] = {"setup": meta, "classifier_reference_capture@5%": reference["B_env"]["capture@5%"],
                          "results": rows, "count_minus_binary_capture@5%": delta}
        print(f"{block}: count - binary capture@5%={delta:+.12f}", flush=True)

    result = {"mode": "exploratory robustness of B1-selected count_poisson",
              "question": "Does the count-vs-binary Poisson capture@5% advantage persist in B2 and B3?",
              "fixed_setup": {"splits": [{"block": b, "train": list(t), "test": s} for b, t, s in SPLITS],
                              "B3_test_label_period": "2026 April-September",
                              "features": "B_env static only", "feature_names": names, "hgb": me.HGB,
                              "seed": 0, "sample_weight_passed": False, "poisson_loss": "poisson",
                              "numpy": np.__version__, "sklearn": sklearn.__version__,
                              "input_sha256": source_hashes, "baseline_tolerance": TOLERANCE,
                              "B1_reference": str(b1_path.relative_to(Path(__file__).resolve().parents[4]))},
              "B1_reference_results": b1["results"], "B2_B3": outputs,
              "decision": decide(differences),
              "limitations": "Point estimates only; B1 model choice was exploratory. Original B2/B3 confirmatory claims remain unchanged. Counts also reflect reporting. B3 is a partial-year label, and no uncertainty interval is estimated."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["decision"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

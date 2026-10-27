"""Reproduce one B1 count-Poisson score vector, then test only E25/E50/E75.

Run from the repository root with the previous B1 input artifacts:
    uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 python \
      projects/akita-bear-risk-grid-100m/scripts/rank_ensemble_b1.py \
      ART_DIR SCORES_NPZ OUT_JSON
Only 2023/2024 labels are loaded. The sole fit recreates a missing saved score
vector with the original count-Poisson settings; it is not a new model search.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import rankdata
import sklearn

import count_target_b1 as prior
import model_eval as me


WEIGHTS = (("E25", 0.25), ("E50", 0.50), ("E75", 0.75))
TOLERANCE = 1e-9


def evaluate_one(scores, y, counts):
    scores = np.asarray(scores)
    y, counts = np.asarray(y), np.asarray(counts)
    if scores.ndim != 1 or y.shape != scores.shape or counts.shape != scores.shape \
            or not np.isfinite(scores).all():
        raise ValueError("scores and 2024 labels/counts must be finite aligned vectors")
    measured = me.evaluate({"B_env": scores}, y, counts, np.empty(0), [], B=0, seed=0)["B_env"]
    return {key: measured[key] for key in prior.METRICS}


def require_reproduction(measured, reference, name, *, saved_float32=False):
    for key in prior.METRICS:
        tolerance = 1e-8 if saved_float32 and key in {"auc", "ap"} else TOLERANCE
        if key not in reference or not np.isfinite(reference[key]) \
                or abs(measured[key] - reference[key]) > tolerance:
            raise ValueError(f"{name} failed to reproduce prior {key}")


def reconstruct_count_scores(fit_fn, Xtr, train_counts, Xte, yte, test_counts,
                             reference):
    """Exactly one original-configuration fit; no output if metrics disagree."""
    model = fit_fn(Xtr, train_counts)
    score = np.asarray(model.predict(Xte))
    measured = evaluate_one(score, yte, test_counts)
    require_reproduction(measured, reference, "count_poisson")
    return score, measured


def percentile_rank(score):
    """Midrank percentile in [0,1], with equal raw scores receiving equal ranks."""
    score = np.asarray(score)
    if score.ndim != 1 or len(score) == 0 or not np.isfinite(score).all():
        raise ValueError("score must be a nonempty finite 1-D vector")
    return (rankdata(score, method="average") - 0.5) / len(score)


def ensemble_scores(classifier_score, poisson_score):
    if np.asarray(classifier_score).shape != np.asarray(poisson_score).shape:
        raise ValueError("classifier and Poisson scores must align")
    cls_rank = percentile_rank(classifier_score)
    count_rank = percentile_rank(poisson_score)
    return {name: (1 - weight) * cls_rank + weight * count_rank
            for name, weight in WEIGHTS}


def choose_best(rows):
    by_name = {row["setting"]: row for row in rows}
    if set(by_name) != {name for name, _ in WEIGHTS}:
        raise ValueError("only E25, E50 and E75 may be compared")
    return max((name for name, _ in WEIGHTS), key=lambda name: by_name[name]["capture@5%"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path, help="existing B1 input artifact directory")
    ap.add_argument("scores_out", type=Path, help="new repo artifact with both B1 score vectors")
    ap.add_argument("out", type=Path, help="small JSON results and provenance")
    args = ap.parse_args()
    if args.scores_out.exists() or args.out.exists():
        raise FileExistsError("score/result output already exists; refuse an unintended second fit")

    project = Path(__file__).resolve().parents[1]
    prior_path = project / "outputs/b1_poisson_target_isolation.json"
    previous = json.loads(prior_path.read_text(encoding="utf-8"))
    setup = previous["setup"]
    if setup["train_year"] != 2023 or setup["test_year"] != 2024 \
            or setup["hgb"] != me.HGB or setup["seed"] != 0 \
            or setup["sample_weight_passed"] is not False \
            or setup["numpy"] != np.__version__ or setup["sklearn"] != sklearn.__version__:
        raise ValueError("runtime or B1 settings differ from prior count-Poisson run")
    source_hashes = {name: prior.sha256(args.art / name) for name in prior.INPUTS}
    if source_hashes != setup["input_sha256"]:
        raise ValueError("B1 source data hashes differ from prior run")
    reference = {row["setting"]: row for row in previous["results"]}
    if "B_env_classifier" not in reference or "count_poisson" not in reference:
        raise ValueError("prior B1 metrics lack required models")

    static, counts, muni = prior.load_b1(args.art)
    Xtr, names, ytr, train_counts = me.design(static, counts, muni, 2023, history=False)
    Xte, test_names, yte, test_counts = me.design(static, counts, muni, 2024, history=False)
    if names != test_names or names != setup["feature_names"] \
            or len(ytr) != setup["n_train"] or len(yte) != setup["n_test"] \
            or int(yte.sum()) != setup["n_test_positive"] \
            or prior.validate_targets(ytr, train_counts)["n_reports"] != 3895:
        raise ValueError("B1 design or label counts differ from prior run")

    baseline_path = args.art / "eval/b1_dev_2023_to_2024_scores.npz"
    with np.load(baseline_path) as saved:
        classifier_score = saved["B_env"]
    classifier_metrics = evaluate_one(classifier_score, yte, test_counts)
    require_reproduction(classifier_metrics, reference["B_env_classifier"], "saved B_env",
                         saved_float32=True)
    print("saved B_env baseline reproduced", flush=True)

    # The only fit in this script. No 2025/2026 arrays are loaded.
    count_score, count_metrics = reconstruct_count_scores(
        prior.fit_poisson, Xtr, train_counts, Xte, yte, test_counts, reference["count_poisson"])
    print("one count_poisson fit reproduced all five prior B1 metrics", flush=True)

    rows = [{"setting": "B_env", **classifier_metrics},
            {"setting": "count_poisson", **count_metrics}]
    ensembles = ensemble_scores(classifier_score, count_score)
    ensemble_rows = [{"setting": name, "count_poisson_rank_weight": weight,
                      **evaluate_one(ensembles[name], yte, test_counts)}
                     for name, weight in WEIGHTS]
    rows.extend(ensemble_rows)
    best = choose_best(ensemble_rows)

    args.scores_out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.scores_out, B_env=classifier_score, count_poisson=count_score)
    with np.load(args.scores_out) as saved:
        if saved.files != ["B_env", "count_poisson"] \
                or not np.array_equal(saved["B_env"], classifier_score) \
                or not np.array_equal(saved["count_poisson"], count_score):
            raise ValueError("saved score artifact failed round-trip validation")
    result = {
        "mode": "B1 exploratory rank ensemble; count-Poisson fit only to recreate missing saved scores",
        "question": "Does a fixed percentile-rank mixture improve B1 capture@5%?",
        "setup": {"train_year": 2023, "test_year": 2024, "n_cells": int(len(yte)),
                  "n_positive": int(yte.sum()), "features": "existing B_env static 28",
                  "feature_names": names, "hgb": me.HGB, "seed": 0,
                  "fit_calls": {"B_env": 0, "count_poisson": 1},
                  "count_target": "2023 cell report count; no sample weight",
                  "percentile_rank": "(scipy.stats.rankdata(score,method=average)-0.5)/n over all prefecture cells; equal scores get equal midranks",
                  "ensemble_weights": {name: weight for name, weight in WEIGHTS},
                  "evaluation": "2024 binary positive cells; existing metrics.rank_order seed=0 and fractional capture boundary",
                  "numpy": np.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
        "provenance": {"prior_b1_json": str(prior_path),
                       "prior_b1_json_sha256": prior.sha256(prior_path),
                       "input_sha256": source_hashes,
                       "saved_benv_scores_npz_sha256": prior.sha256(baseline_path),
                       "reproduced_scores_npz": str(args.scores_out),
                       "reproduced_scores_npz_sha256": prior.sha256(args.scores_out),
                       "script": "projects/akita-bear-risk-grid-100m/scripts/rank_ensemble_b1.py",
                       "script_sha256": prior.sha256(Path(__file__)),
                       "model_eval_py_sha256": prior.sha256(Path(me.__file__)),
                       "count_target_b1_py_sha256": prior.sha256(Path(prior.__file__))},
        "results": rows,
        "selection": {"best_ensemble": best,
                      "best_capture@5%": next(r["capture@5%"] for r in ensemble_rows if r["setting"] == best),
                      "tie_break": "E25, then E50, then E75 on exact capture@5% ties",
                      "tested_only": [name for name, _ in WEIGHTS]},
        "limitations": "B1 is an exploratory year chosen for model development. The selected weight is not independently validated; 2025/2026 were not used. Refit is only to materialize prior missing count-Poisson cell scores, not a new model search."
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({r["setting"]: r["capture@5%"] for r in rows} | {"best": best},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

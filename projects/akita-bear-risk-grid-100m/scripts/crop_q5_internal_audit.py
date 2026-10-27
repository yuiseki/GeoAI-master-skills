"""Audit internal crop-Q5 ranking in saved B_env B2/B3 scores only.

Run from the repository root:
    uvx --with numpy --with scipy --with scikit-learn python \
      projects/akita-bear-risk-grid-100m/scripts/crop_q5_internal_audit.py ART_DIR OUT_JSON
"""

import argparse
import json
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

import false_negative_audit as previous
import metrics as mt


FRACTIONS = (0.05, 0.10, 0.20)


def q5_mask(crop, cutoff):
    crop = np.asarray(crop)
    if crop.ndim != 1 or not np.issubdtype(crop.dtype, np.number):
        raise ValueError("crop must be a numeric 1-D array")
    return np.isfinite(crop) & (crop > cutoff)


def order_within(global_order, mask):
    """Filter the original full-prefecture order; never break ties again."""
    global_order, mask = np.asarray(global_order), np.asarray(mask)
    return global_order[mask[global_order]]


def _stratum_summary(score, positive, global_order, mask, global_top):
    selected = order_within(global_order, mask)
    n = len(selected)
    n_pos = int(positive[mask].sum())
    n_top_global = int(np.count_nonzero(global_top & mask))
    n_captured_global = int(np.count_nonzero(global_top & mask & positive))
    # The sorted labels already inherit the saved-score ordering and global tie break.
    sorted_y = positive[selected]
    captures = {f"capture_at_{int(100 * k)}_percent_within_stratum":
                mt.capture(np.arange(n), sorted_y, k) if n_pos else None
                for k in FRACTIONS}
    return {"n_cells": n, "n_positive": n_pos,
            "positive_rate": n_pos / n if n else None,
            "auc": float(roc_auc_score(positive[mask], score[mask])) if 0 < n_pos < n else None,
            "ap": float(average_precision_score(positive[mask], score[mask])) if n_pos else None,
            **captures,
            "n_global_top5_cells": n_top_global,
            "global_top5_allocation_rate": n_top_global / n if n else None,
            "n_global_top5_captured_positive": n_captured_global,
            "global_top5_recall_in_stratum": n_captured_global / n_pos if n_pos else None}


def audit_year(score, positive, crop, cutoff, *, expected_capture, expected_q5_cells,
               expected_q5_positive, expected_q5_global_captured):
    score, positive, crop = np.asarray(score), np.asarray(positive), np.asarray(crop)
    n = len(score)
    if n == 0 or score.ndim != 1 or positive.shape != (n,) or crop.shape != (n,) \
            or positive.dtype != bool or not np.isfinite(score).all():
        raise ValueError("score, labels and crop must be valid aligned 1-D arrays")
    q5 = q5_mask(crop, cutoff)
    if int(q5.sum()) != expected_q5_cells or int(np.count_nonzero(q5 & positive)) != expected_q5_positive:
        raise ValueError("crop Q5 cells/positives differ from previous fixed strata")
    order = mt.rank_order(score, seed=0)
    overall = mt.capture(order, positive, 0.05)
    if abs(overall - expected_capture) > 1e-9:
        raise ValueError("saved B_env overall capture@5% did not reproduce")
    top = np.zeros(n, dtype=bool)
    top[order[:int(np.ceil(0.05 * n))]] = True
    if int(np.count_nonzero(q5 & positive & top)) != expected_q5_global_captured:
        raise ValueError("crop Q5 global top-5% captured positives differ from previous audit")
    strata = {"crop_Q5": _stratum_summary(score, positive, order, q5, top),
              "non_Q5": _stratum_summary(score, positive, order, ~q5, top)}
    if sum(s["n_cells"] for s in strata.values()) != n \
            or sum(s["n_positive"] for s in strata.values()) != int(positive.sum()) \
            or sum(s["n_global_top5_cells"] for s in strata.values()) != int(top.sum()):
        raise ValueError("Q5/non-Q5 partition does not reproduce prefecture totals")
    return {"n_cells": n, "n_positive": int(positive.sum()),
            "n_crop_missing": int(np.count_nonzero(~np.isfinite(crop))),
            "overall_capture_at_5": overall,
            "n_global_top5_cells": int(top.sum()), "strata": strata}


def interpret(years):
    q5 = [years[block]["strata"]["crop_Q5"] for block in ("B2", "B3")]
    return {"internal_rank_signal_both_years":
            all(s["auc"] is not None and s["auc"] > 0.5
                and s["ap"] is not None and s["ap"] > s["positive_rate"]
                and s["capture_at_5_percent_within_stratum"] is not None
                and s["capture_at_5_percent_within_stratum"] > 0.05 for s in q5),
            "allocation_below_5_percent_both_years":
            all(s["global_top5_allocation_rate"] is not None
                and s["global_top5_allocation_rate"] < 0.05 for s in q5)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    project = Path(__file__).resolve().parents[1]
    prior_path = project / "outputs/b2_b3_feature_stratified_capture.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    cut_b2 = prior["years"]["B2"]["features"]["crop"]["cutpoints_q20_q40_q60_q80"]
    cut_b3 = prior["years"]["B3"]["features"]["crop"]["cutpoints_q20_q40_q60_q80"]
    if cut_b2 != cut_b3 or len(cut_b2) != 4:
        raise ValueError("prior crop quintile cutpoints are not fixed across years")
    cutoff = cut_b2[-1]
    input_names = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
                   "reports_by_year.npz", "grid_mask.npz")
    hashes = {name: previous.sha256(args.art / name) for name in input_names}
    if any(hashes[name] != prior["input_sha256"][name] for name in input_names):
        raise ValueError("source artifacts differ from previous strata audit")
    with np.load(args.art / "grid_mask.npz") as grid:
        inside = grid["muni"] >= 0
    with np.load(args.art / "worldcover.npz") as wc:
        # Existing features.static_features uses exactly this cast for `crop`.
        crop = wc["f40"].astype(np.float32)[inside]
    if int(inside.sum()) != prior["years"]["B2"]["n_cells"]:
        raise ValueError("prefecture grid size differs from previous audit")

    years = {}
    with np.load(args.art / "reports_by_year.npz") as labels:
        for block, (year, stem) in previous.SPLITS.items():
            score_path = args.art / "eval" / f"{stem}_scores.npz"
            eval_path = args.art / "eval" / f"{stem}.json"
            ref = json.loads(eval_path.read_text(encoding="utf-8"))
            if ref["setup"]["test"] != year or ref["n_cells"] != int(inside.sum()):
                raise ValueError(f"{block} saved evaluation metadata differs")
            for name, path in ((f"eval/{stem}_scores.npz", score_path),
                               (f"eval/{stem}.json", eval_path)):
                hashes[name] = previous.sha256(path)
                if hashes[name] != prior["input_sha256"][name]:
                    raise ValueError(f"{block} saved scores differ from previous audit")
            with np.load(score_path) as scores:
                score = scores["B_env"]
            positive = labels[f"c{year}"][inside] > 0
            if int(positive.sum()) != ref["n_pos_cells"]:
                raise ValueError(f"{block} positive labels differ from saved evaluation")
            q5_prior = next(r for r in prior["years"][block]["features"]["crop"]["strata"]
                            if r["stratum"] == "Q5")
            years[block] = {"test_year": year,
                            "test_label_period": "April-September" if year == 2026 else "full fiscal year",
                            **audit_year(score, positive, crop, cutoff,
                                         expected_capture=ref["B_env"]["capture@5%"],
                                         expected_q5_cells=q5_prior["n_cells"],
                                         expected_q5_positive=q5_prior["n_positive"],
                                         expected_q5_global_captured=q5_prior["n_captured_positive"])}
    result = {"mode": "exploratory descriptive diagnostic; saved scores only",
              "question": "Does saved B_env retain internal ranking signal in fixed crop Q5?",
              "definition": {"crop_Q5": f"finite WorldCover 2021 class-40 cell fraction > {cutoff} (prior fixed q80)",
                             "non_Q5": "complement of crop Q5, including missing if present",
                             "internal_order": "subsequence of statewide metrics.rank_order(saved B_env score,seed=0); no new tie break",
                             "capture": "fractional boundary at 5%, 10%, 20% of stratum cells; denominator positive cells in same stratum",
                             "global_top5_allocation_rate": "number of stratum cells among statewide top ceil(5%) / all stratum cells",
                             "signal_rule": "AUC>0.5, AP>stratum prevalence, internal capture@5%>0.05 in both B2/B3",
                             "allocation_rule": "statewide top-5% allocation rate in Q5 <0.05 in both B2/B3"},
              "provenance": {"prior_strata_json": str(prior_path),
                             "prior_strata_json_sha256": previous.sha256(prior_path),
                             "input_sha256": hashes,
                             "script": "projects/akita-bear-risk-grid-100m/scripts/crop_q5_internal_audit.py",
                             "script_sha256": previous.sha256(Path(__file__)),
                             "metrics_py_sha256": previous.sha256(Path(mt.__file__)),
                             "numpy": np.__version__, "scikit_learn": sklearn.__version__},
              "years": years, "interpretation": interpret(years),
              "limitations": "B2/B3 and crop Q5 were inspected in earlier audits, so these are descriptive post-hoc diagnostics, not independent tests. Internal 5% and statewide 5% are different area budgets; internal signal alone does not establish gains from policy reallocation. B3 is April-September only. Reporting bias, spatial dependence, and model-feature selection remain."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"interpretation": result["interpretation"],
                      "q5": {block: years[block]["strata"]["crop_Q5"] for block in years}},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

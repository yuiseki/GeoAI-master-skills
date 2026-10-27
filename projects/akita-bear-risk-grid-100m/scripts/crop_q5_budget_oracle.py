"""Diagnostic label-aware allocation oracle for saved B_env crop-Q5/non-Q5 ranks.

Run from repository root:
    uvx --with numpy --with scipy python \
      projects/akita-bear-risk-grid-100m/scripts/crop_q5_budget_oracle.py ART_DIR OUT_JSON
The oracle uses test labels and is not an evaluated predictive model.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import false_negative_audit as previous
import metrics as mt


def audit_year(score, positive, q5, *, expected_fractional_capture,
               expected_q5_cells, expected_q5_positive,
               expected_ceil_q5_selected, expected_ceil_q5_captured):
    """Enumerate every feasible integer split of the same floor(5%) budget."""
    score, positive, q5 = np.asarray(score), np.asarray(positive), np.asarray(q5)
    n = len(score)
    if n == 0 or score.ndim != 1 or positive.shape != (n,) or q5.shape != (n,) \
            or positive.dtype != bool or q5.dtype != bool or not np.isfinite(score).all():
        raise ValueError("score, labels and Q5 membership must be aligned and valid")
    n_positive = int(positive.sum())
    if n_positive == 0 or int(q5.sum()) != expected_q5_cells \
            or int(np.count_nonzero(q5 & positive)) != expected_q5_positive:
        raise ValueError("Q5 cells/positives differ from prior fixed-stratum audit")
    order = mt.rank_order(score, seed=0)
    fractional = mt.capture(order, positive, 0.05)
    if abs(fractional - expected_fractional_capture) > 1e-9:
        raise ValueError("saved fractional capture@5% did not reproduce")
    ceil_top = order[:int(np.ceil(0.05 * n))]
    if int(q5[ceil_top].sum()) != expected_ceil_q5_selected \
            or int(np.count_nonzero(q5[ceil_top] & positive[ceil_top])) != expected_ceil_q5_captured:
        raise ValueError("Q5 ceil-top membership differs from previous internal audit")

    budget = int(np.floor(0.05 * n))
    current_top = order[:budget]
    current_q5 = int(q5[current_top].sum())
    current_captured = int(positive[current_top].sum())
    # Preserve the original global score order and its already-fixed tie breaks.
    q_order = order[q5[order]]
    non_order = order[~q5[order]]
    low = max(0, budget - len(non_order))
    high = min(budget, len(q_order))
    ks = np.arange(low, high + 1, dtype=np.int64)
    q_cumulative = np.r_[0, np.cumsum(positive[q_order], dtype=np.int64)]
    non_cumulative = np.r_[0, np.cumsum(positive[non_order], dtype=np.int64)]
    captured = q_cumulative[ks] + non_cumulative[budget - ks]
    captures = captured / n_positive
    if not low <= current_q5 <= high or int(captured[current_q5 - low]) != current_captured:
        raise ValueError("fixed-order allocation curve does not reproduce current global top-K")
    best_count = int(captured.max())
    best_ks = ks[captured == best_count]
    representative = min((int(k) for k in best_ks), key=lambda k: (abs(k - current_q5), k))
    return {
        "n_cells": n, "n_positive": n_positive, "n_q5_cells": int(q5.sum()),
        "n_non_q5_cells": int((~q5).sum()), "budget_cells": budget,
        "actual_selected_cell_fraction": budget / n,
        "original_fractional_capture_at_5": fractional,
        "feasible_q5_allocation_min": low, "feasible_q5_allocation_max": high,
        "current": {"q5_selected_cells": current_q5,
                    "non_q5_selected_cells": budget - current_q5,
                    "q5_share_of_budget": current_q5 / budget if budget else None,
                    "captured_positive": current_captured,
                    "capture": current_captured / n_positive},
        "oracle": {"q5_selected_cells": representative,
                   "non_q5_selected_cells": budget - representative,
                   "q5_share_of_budget": representative / budget if budget else None,
                   "captured_positive": best_count,
                   "capture": best_count / n_positive,
                   "n_tied_optimal_allocations": int(len(best_ks)),
                   "all_optimal_q5_cells_min": int(best_ks.min()),
                   "all_optimal_q5_cells_max": int(best_ks.max())},
        "oracle_minus_current": {"q5_selected_cells": representative - current_q5,
                                 "captured_positive": best_count - current_captured,
                                 "capture": (best_count - current_captured) / n_positive},
        "curve": {"q5_selected_cells_start": low, "q5_selected_cells_step": 1,
                  "captured_positive_by_q5_cells": captured.tolist(),
                  "capture_by_q5_cells": captures.tolist()},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    project = Path(__file__).resolve().parents[1]
    strata_path = project / "outputs/b2_b3_feature_stratified_capture.json"
    internal_path = project / "outputs/b2_b3_crop_q5_internal_audit.json"
    strata = json.loads(strata_path.read_text(encoding="utf-8"))
    internal = json.loads(internal_path.read_text(encoding="utf-8"))
    if previous.sha256(strata_path) != internal["provenance"]["prior_strata_json_sha256"]:
        raise ValueError("prior strata JSON differs from prior internal audit")
    cut_b2 = strata["years"]["B2"]["features"]["crop"]["cutpoints_q20_q40_q60_q80"]
    cut_b3 = strata["years"]["B3"]["features"]["crop"]["cutpoints_q20_q40_q60_q80"]
    if cut_b2 != cut_b3 or len(cut_b2) != 4:
        raise ValueError("prior crop quintile boundary differs across years")
    cutoff = cut_b2[-1]
    input_names = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
                   "reports_by_year.npz", "grid_mask.npz")
    hashes = {name: previous.sha256(args.art / name) for name in input_names}
    if any(hashes[name] != internal["provenance"]["input_sha256"][name] for name in input_names):
        raise ValueError("source artifacts differ from previous internal audit")
    with np.load(args.art / "grid_mask.npz") as grid:
        inside = grid["muni"] >= 0
    with np.load(args.art / "worldcover.npz") as wc:
        crop = wc["f40"].astype(np.float32)[inside]
    q5 = np.isfinite(crop) & (crop > cutoff)
    if int(inside.sum()) != strata["years"]["B2"]["n_cells"]:
        raise ValueError("prefecture grid size differs from prior strata")

    years = {}
    with np.load(args.art / "reports_by_year.npz") as labels:
        for block, (year, stem) in previous.SPLITS.items():
            score_path = args.art / "eval" / f"{stem}_scores.npz"
            eval_path = args.art / "eval" / f"{stem}.json"
            ref = json.loads(eval_path.read_text(encoding="utf-8"))
            if ref["setup"]["test"] != year or ref["n_cells"] != int(inside.sum()):
                raise ValueError(f"{block} reference evaluation metadata differs")
            for name, path in ((f"eval/{stem}_scores.npz", score_path),
                               (f"eval/{stem}.json", eval_path)):
                hashes[name] = previous.sha256(path)
                if hashes[name] != internal["provenance"]["input_sha256"][name]:
                    raise ValueError(f"{block} saved score provenance differs")
            with np.load(score_path) as scores:
                score = scores["B_env"]
            positive = labels[f"c{year}"][inside] > 0
            if int(positive.sum()) != ref["n_pos_cells"]:
                raise ValueError(f"{block} labels differ from saved evaluation")
            q5_prior = next(row for row in strata["years"][block]["features"]["crop"]["strata"]
                            if row["stratum"] == "Q5")
            internal_q5 = internal["years"][block]["strata"]["crop_Q5"]
            if q5_prior["n_cells"] != internal_q5["n_cells"] \
                    or q5_prior["n_positive"] != internal_q5["n_positive"] \
                    or q5_prior["n_captured_positive"] != internal_q5["n_global_top5_captured_positive"]:
                raise ValueError(f"{block} prior Q5 results disagree")
            years[block] = {"test_year": year,
                            "test_label_period": "April-September" if year == 2026 else "full fiscal year",
                            **audit_year(score, positive, q5,
                                         expected_fractional_capture=ref["B_env"]["capture@5%"],
                                         expected_q5_cells=q5_prior["n_cells"],
                                         expected_q5_positive=q5_prior["n_positive"],
                                         expected_ceil_q5_selected=internal_q5["n_global_top5_cells"],
                                         expected_ceil_q5_captured=q5_prior["n_captured_positive"])}
    result = {
        "mode": "exploratory diagnostic oracle using test labels; not an evaluated model",
        "question": "How much can a fixed 5% cell budget gain by reallocating between fixed crop Q5 and non-Q5?",
        "definition": {"crop_q5": f"finite WorldCover 2021 class-40 fraction > {cutoff}",
                       "budget": "K=floor(0.05*n_prefecture_cells), identical for current and all allocations",
                       "within_stratum_order": "subsequence of original statewide metrics.rank_order(saved B_env score,seed=0)",
                       "capture_by_q5_cells": "at each integer k: positives among first k Q5 plus first K-k non-Q5, divided by all prefecture positives",
                       "oracle_tie_break": "nearest optimal k to current global top-K allocation, then smaller k; min/max of all ties also stored",
                       "original_fractional_capture": "saved evaluation metric with fractional boundary cell, reference only"},
        "provenance": {"prior_strata_json": str(strata_path),
                       "prior_strata_json_sha256": previous.sha256(strata_path),
                       "prior_internal_json": str(internal_path),
                       "prior_internal_json_sha256": previous.sha256(internal_path),
                       "input_sha256": hashes,
                       "script": "projects/akita-bear-risk-grid-100m/scripts/crop_q5_budget_oracle.py",
                       "script_sha256": previous.sha256(Path(__file__)),
                       "metrics_py_sha256": previous.sha256(Path(mt.__file__)),
                       "numpy": np.__version__},
        "years": years,
        "limitations": "The oracle chooses allocation after observing B2/B3 labels. Its gain is an in-sample ceiling, not out-of-sample improvement or a deployable policy. Fixed within-stratum ranks cannot repair their own mistakes. B3 labels cover April-September only; observation bias and spatial dependence remain."
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n",
                        encoding="utf-8")
    print(json.dumps({block: {"current": years[block]["current"],
                              "oracle": years[block]["oracle"],
                              "gain": years[block]["oracle_minus_current"]}
                      for block in years}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

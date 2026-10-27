"""Audit fold-local capture from reproduced, saved B2/B3 OOF cell scores only.

From the repository root:
    uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 python \
      projects/akita-bear-risk-grid-100m/scripts/fold_local_oof_audit.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/akita-bear-risk-grid-100m \
      artifacts/akita-bear-risk-grid-100m/eval/b2_b3_spatial_oof_scores.npz \
      projects/akita-bear-risk-grid-100m/outputs/b2_b3_fold_local_oof_audit.json
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import metrics as mt
import same_year_spatial_oof as spatial

FRACTIONS = (0.01, 0.05, 0.10)


def fold_local_capture(scores, positive, folds, fractions=FRACTIONS):
    """Allocate k% of each held-out fold, preserving the global tie-breaking key."""
    scores, positive, folds = map(np.asarray, (scores, positive, folds))
    n = len(scores)
    if scores.shape != (n,) or n == 0 or not np.isfinite(scores).all() \
            or positive.shape != (n,) or positive.dtype != bool or folds.shape != (n,) \
            or not np.issubdtype(folds.dtype, np.integer) or len(np.unique(folds)) < 2 \
            or int(positive.sum()) == 0:
        raise ValueError("scores, binary labels and held-out folds must be valid and aligned")
    order = mt.rank_order(scores, seed=0)
    rank = np.empty(n, dtype=np.int32)
    rank[order] = np.arange(n, dtype=np.int32)
    global_capture = {}
    local_capture = {}
    deltas = {}
    rows = []
    credits = {k: 0.0 for k in fractions}
    n_positive = int(positive.sum())
    for f in sorted(np.unique(folds).tolist()):
        indices = np.flatnonzero(folds == f)
        local_order = np.argsort(rank[indices])
        y = positive[indices]
        n_fold = len(indices)
        n_pos_fold = int(y.sum())
        row = {"fold": int(f), "n_cells": n_fold, "n_positive": n_pos_fold,
               "selected_cells": {}, "captured_positive_integer": {},
               "captured_positive_equivalent": {}, "recall": {}}
        for k in fractions:
            key = f"{int(round(100 * k))}%"
            boundary = k * n_fold
            whole = int(np.floor(boundary))
            partial = boundary - whole
            selected = int(np.ceil(boundary))
            captured_equivalent = float(y[local_order[:whole]].sum())
            if partial > 0:
                captured_equivalent += float(partial * y[local_order[whole]])
            captured_integer = int(y[local_order[:selected]].sum())
            row["selected_cells"][key] = selected
            row["captured_positive_integer"][key] = captured_integer
            row["captured_positive_equivalent"][key] = captured_equivalent
            row["recall"][key] = (captured_equivalent / n_pos_fold if n_pos_fold else None)
            credits[k] += captured_equivalent
        rows.append(row)
    for k in fractions:
        key = f"capture@{int(round(100 * k))}%"
        global_capture[key] = mt.capture(order, positive, k)
        local_capture[key] = credits[k] / n_positive
        deltas[key] = local_capture[key] - global_capture[key]
    return {"global": global_capture, "fold_local": local_capture,
            "delta_fold_local_minus_global": deltas, "folds": rows}


def load_original_folds(grid_path, fold_path, reference):
    """Recover the original per-cell fold from the committed block table."""
    expected = reference["setup"]["input_sha256"]
    if spatial.sha256(grid_path) != expected["grid_mask.npz"] \
            or spatial.sha256(fold_path) != expected["folds.csv"]:
        raise ValueError("grid or fold-table provenance differs from original OOF run")
    with np.load(grid_path) as grid:
        inside = grid["muni"] >= 0
    iy, ix = np.nonzero(inside)
    blocks = (ix // 100) * 10000 + iy // 100
    with fold_path.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    table = {int(row["block"]): (int(row["fold"]), int(row["n_cells"])) for row in records}
    unique, inverse, counts = np.unique(blocks, return_inverse=True, return_counts=True)
    if len(records) != len(table) or set(table) != set(unique.tolist()) \
            or any(table[int(block)][1] != int(count) for block, count in zip(unique, counts)):
        raise ValueError("original block-fold table does not match grid")
    fold_by_block = np.array([table[int(block)][0] for block in unique], dtype=np.int8)
    if set(fold_by_block.tolist()) != set(range(5)):
        raise ValueError("original table is not five folds")
    return inside, fold_by_block[inverse]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("scores", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    previous_path = project / "outputs/b2_b3_same_year_spatial_oof.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    fold_path = project / "outputs/b2_b3_same_year_spatial_oof_folds.csv"
    inside, folds = load_original_folds(args.art / "grid_mask.npz", fold_path, previous)
    label_path = args.art / "reports_by_year.npz"
    if spatial.sha256(label_path) != previous["setup"]["input_sha256"]["reports_by_year.npz"]:
        raise ValueError("labels differ from original OOF run")
    years = {}
    with np.load(args.scores) as saved, np.load(label_path) as labels:
        if set(saved.files) != set(spatial.SPLITS):
            raise ValueError("saved score file must contain only B2 and B3")
        for block_name, (year, _) in spatial.SPLITS.items():
            score = saved[block_name]
            positive = labels[f"c{year}"][inside] > 0
            old = previous["years"][block_name]
            if score.dtype != np.float64 or score.shape != (old["n_cells"],) \
                    or positive.shape != score.shape or int(positive.sum()) != old["n_positive"]:
                raise ValueError(f"{block_name}: score or label array does not match original OOF")
            checked = spatial.score_metrics(score, positive)
            spatial.assert_reproduced(checked, old["same_year_spatial_oof"], block_name)
            result = fold_local_capture(score, positive, folds)
            for row, expected in zip(result["folds"], old["fold_diagnostics"]):
                if row["fold"] != expected["fold"] or row["n_cells"] != expected["n_test"] \
                        or row["n_positive"] != expected["positive_test"]:
                    raise ValueError(f"{block_name}: fold counts differ from original OOF")
            result["year"] = year
            result["temporal_B_env_capture@5%"] = old["temporal_B_env"]["capture@5%"]
            result["fold_local_minus_temporal_capture@5%"] = (
                result["fold_local"]["capture@5%"] - result["temporal_B_env_capture@5%"])
            years[block_name] = result
    output = {"purpose": "diagnostic fold-local allocation of already reproduced same-year OOF scores",
              "method": "original global rank_order(seed=0), restricted to each held-out fold; fractional boundary as in metrics.capture",
              "fractions": list(FRACTIONS), "input": {
                  "original_oof_json": str(previous_path), "original_oof_json_sha256": spatial.sha256(previous_path),
                  "fold_table": str(fold_path), "fold_table_sha256": spatial.sha256(fold_path),
                  "scores_npz": str(args.scores), "scores_npz_sha256": spatial.sha256(args.scores),
                  "labels_sha256": spatial.sha256(label_path)}, "years": years,
              "limitations": ["fold-local has a separate area budget per fold, not one freely transferable prefecture-wide budget",
                              "a gain can reflect fold score scale or spatial budget allocation; it is not solely a calibration effect",
                              "same-year OOF remains a diagnostic, not a deployable future-year forecast"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, result in years.items():
        print(name, result["global"]["capture@5%"], result["fold_local"]["capture@5%"],
              result["delta_fold_local_minus_global"]["capture@5%"])


if __name__ == "__main__":
    main()

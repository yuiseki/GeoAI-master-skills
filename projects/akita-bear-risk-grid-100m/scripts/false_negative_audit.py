"""Audit missed positive cells in saved B_env B2/B3 scores; never fit a model.

Run from the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy python \
      projects/akita-bear-risk-grid-100m/scripts/false_negative_audit.py ART_DIR OUT_JSON
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.spatial import cKDTree

import metrics as mt


SPLITS = {
    "B2": (2025, "b2_confirm_2023-2024_to_2025"),
    "B3": (2026, "b3_confirm_2023-2025_to_2026"),
}
RANK_BINS = ("5-10%", "10-25%", "25-50%", "50-100%")
DISTANCES_M = (100, 300, 500, 1000)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize(score, positive, ix, iy, *, size_m, reference_capture):
    """Summarize rank/distance of binary positive cells outside top ceil(5%)."""
    score = np.asarray(score)
    positive = np.asarray(positive)
    ix, iy = np.asarray(ix), np.asarray(iy)
    n = len(score)
    if any(a.ndim != 1 or len(a) != n for a in (score, positive, ix, iy)):
        raise ValueError("scores, labels and grid coordinates must be aligned 1-D arrays")
    if n == 0 or not np.issubdtype(positive.dtype, np.bool_) or not np.isfinite(score).all() \
            or not np.isfinite(ix).all() or not np.isfinite(iy).all() or size_m <= 0:
        raise ValueError("invalid scores, binary labels, grid coordinates or cell size")
    n_positive = int(positive.sum())
    if n_positive == 0:
        raise ValueError("no positive cells to audit")

    order = mt.rank_order(score, seed=0)
    capture = mt.capture(order, positive, 0.05)
    if reference_capture is not None and abs(capture - reference_capture) > 1e-9:
        raise ValueError(f"saved score capture@5% does not reproduce: {capture:.12f}"
                         f" vs {reference_capture:.12f}")
    n_top = int(np.ceil(0.05 * n))
    rank = np.empty(n, dtype=np.int32)
    rank[order] = np.arange(n, dtype=np.int32)
    missed = positive & (rank >= n_top)
    missed_indices = np.flatnonzero(missed)
    captured = n_positive - len(missed_indices)
    if abs(captured / n_positive - capture) > 1 / n_positive + 1e-12:
        raise ValueError("binary top-5% membership disagrees with fractional capture")

    percentile = rank[missed_indices] / n
    bucket_ids = np.searchsorted([0.10, 0.25, 0.50], percentile, side="right")
    bin_counts = {label: int(np.count_nonzero(bucket_ids == j)) for j, label in enumerate(RANK_BINS)}

    # Grid index differences multiplied by projected 100 m cell size equal
    # EPSG:6678 centre-to-centre Euclidean metres; origins cancel out.
    top_points = np.column_stack((ix[order[:n_top]], iy[order[:n_top]]))
    miss_points = np.column_stack((ix[missed_indices], iy[missed_indices]))
    distances = cKDTree(top_points).query(miss_points)[0] * size_m if len(missed_indices) else np.empty(0)
    within = {str(t): {"count": int(np.count_nonzero(distances <= t)),
                       "share": float(np.mean(distances <= t)) if len(distances) else None}
              for t in DISTANCES_M}
    rank_distance = {str(t): {label: int(np.count_nonzero((bucket_ids == j) & (distances <= t)))
                              for j, label in enumerate(RANK_BINS)}
                     for t in DISTANCES_M}
    return {
        "n_cells": n, "n_top5_cells": n_top, "n_positive": n_positive,
        "n_captured_positive": captured, "n_missed_positive": int(len(missed_indices)),
        "capture_at_5_from_saved_scores": capture,
        "capture_at_5_binary_top_set": captured / n_positive,
        "rank_bins_counts": bin_counts,
        "rank_bins_shares_of_missed": {key: value / len(missed_indices) if len(missed_indices) else None
                                        for key, value in bin_counts.items()},
        "distance_m": {"median": float(np.median(distances)) if len(distances) else None,
                       "p90": float(np.percentile(distances, 90)) if len(distances) else None},
        "within_distance_m": within,
        "rank_bins_within_distance_counts": rank_distance,
    }


def decide_priority(summaries):
    n = sum(item["n_missed_positive"] for item in summaries.values())
    near_rank = sum(item["rank_bins_counts"]["5-10%"] for item in summaries.values())
    near_space = sum(item["within_distance_m"]["300"]["count"] for item in summaries.values())
    if n <= 0:
        raise ValueError("no missed positive cells across years")
    if near_rank > n / 2:
        priority = "ranking_improvement"
    elif near_space > n / 2:
        priority = "position_accuracy_audit"
    else:
        priority = "new_explanatory_variables"
    return {"priority": priority, "pooled_n_missed": n,
            "pooled_5_to_10_rank_count": near_rank, "pooled_5_to_10_rank_share": near_rank / n,
            "pooled_within_300m_count": near_space, "pooled_within_300m_share": near_space / n,
            "rule": "5-10% rank majority, else <=300m majority, else new explanatory variables"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path, help="existing artifact directory")
    ap.add_argument("out", type=Path, help="output JSON")
    args = ap.parse_args()

    grid_path = args.art / "grid.json"
    mask_path = args.art / "grid_mask.npz"
    report_path = args.art / "reports_by_year.npz"
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    if grid["crs"] != "EPSG:6678" or grid["size"] != 100:
        raise ValueError("expected EPSG:6678 100 m grid")
    with np.load(mask_path) as file:
        mask = file["muni"] >= 0
    if mask.shape != (grid["ny"], grid["nx"]) or int(mask.sum()) != grid["cells_in_prefecture"]:
        raise ValueError("grid mask and metadata disagree")
    iy, ix = np.nonzero(mask)  # same C-order used by model_eval.design
    summaries, hashes = {}, {name: sha256(path) for name, path in
                            (("grid.json", grid_path), ("grid_mask.npz", mask_path),
                             ("reports_by_year.npz", report_path))}
    with np.load(report_path) as reports:
        for block, (year, stem) in SPLITS.items():
            scores_path = args.art / "eval" / f"{stem}_scores.npz"
            eval_path = args.art / "eval" / f"{stem}.json"
            reference = json.loads(eval_path.read_text(encoding="utf-8"))
            if reference["setup"]["test"] != year or reference["n_cells"] != len(ix):
                raise ValueError(f"{block} evaluation metadata differs from grid")
            with np.load(scores_path) as scores:
                score = scores["B_env"]
            positive = reports[f"c{year}"][mask] > 0
            if int(positive.sum()) != reference["n_pos_cells"]:
                raise ValueError(f"{block} positive labels differ from evaluation metadata")
            summaries[block] = {"test_year": year,
                                "test_label_period": "April-September" if year == 2026 else "full fiscal year",
                                "reference_capture@5%": reference["B_env"]["capture@5%"],
                                **summarize(score, positive, ix, iy, size_m=grid["size"],
                                            reference_capture=reference["B_env"]["capture@5%"])}
            hashes.update({f"eval/{stem}.json": sha256(eval_path),
                           f"eval/{stem}_scores.npz": sha256(scores_path)})
            print(f"{block}: missed {summaries[block]['n_missed_positive']} / {int(positive.sum())}"
                  f" positives; median distance {summaries[block]['distance_m']['median']:.1f} m", flush=True)

    result = {"mode": "diagnostic; no training or threshold tuning",
              "question": "Are saved B_env false negatives close in rank or geography to the top 5%?",
              "implementation": {"script": "projects/akita-bear-risk-grid-100m/scripts/false_negative_audit.py",
                                 "script_sha256": sha256(Path(__file__)),
                                 "metrics_py_sha256": sha256(Path(mt.__file__)),
                                 "numpy": np.__version__, "scipy": scipy.__version__},
              "definition": {"grid_crs": grid["crs"], "cell_size_m": grid["size"],
                             "top5_membership": "first ceil(0.05*n) cells in metrics.rank_order(score,seed=0)",
                             "rank_percentile": "zero-based rank / n_cells",
                             "rank_bins": list(RANK_BINS), "distance": "nearest selected cell centre, Euclidean EPSG:6678 metres",
                             "distance_thresholds_m": list(DISTANCES_M),
                             "distance_denominator": "missed positive cells in each year"},
              "input_sha256": hashes, "years": summaries, "priority": decide_priority(summaries),
              "limitations": "Cell-centre Euclidean distance is not road distance or the reporting-coordinate error. B3 labels cover only April-September. Counts reflect reported presence, not all bear encounters. This audit does not establish why cells were missed."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["priority"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

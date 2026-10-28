"""Evaluate saved B_env scores with a fixed-area seed-and-dilate selection rule.

Run from repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/fixed_area_dilation.py ART_DIR OUT_JSON

No fitting, new feature, score adjustment, or budget tuning is performed.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import false_negative_audit as prior
import metrics as mt


RADII_M = (100, 300, 500)
BUDGET_FRACTION = 0.05


def greedy_union(order, ix, iy, mask, *, radius_m, size_m, budget_cells):
    """Accept ranked seed disks until the next disk would exceed budget.

    Returns a 2-D selected mask and run metadata. Seeds already inside the
    selected union are still considered, as their disks may add other cells.
    """
    order, ix, iy, mask = np.asarray(order), np.asarray(ix), np.asarray(iy), np.asarray(mask)
    n = int(mask.sum())
    if mask.ndim != 2 or mask.dtype != bool or len(order) != n or len(ix) != n or len(iy) != n \
            or order.ndim != 1 or ix.ndim != 1 or iy.ndim != 1:
        raise ValueError("rank order and grid coordinates must be aligned with the 2-D mask")
    if budget_cells < 1 or budget_cells > n:
        raise ValueError("budget must be between 1 and the number of inside cells")
    if radius_m < 0 or size_m <= 0 or radius_m / size_m != round(radius_m / size_m):
        raise ValueError("radius must be a nonnegative whole-cell multiple")
    if np.unique(order).size != n or order.min() != 0 or order.max() != n - 1:
        raise ValueError("rank order must be a permutation of inside cells")
    if np.any(ix < 0) or np.any(iy < 0) or np.any(ix >= mask.shape[1]) or np.any(iy >= mask.shape[0]) \
            or not np.all(mask[iy, ix]):
        raise ValueError("grid coordinates must refer to inside cells")

    radius_cells = int(round(radius_m / size_m))
    dy, dx = np.mgrid[-radius_cells:radius_cells + 1, -radius_cells:radius_cells + 1]
    keep = dx * dx + dy * dy <= radius_cells * radius_cells
    dx, dy = dx[keep], dy[keep]
    selected = np.zeros_like(mask)
    selected_flat = selected.ravel()
    width, height = mask.shape[1], mask.shape[0]
    n_selected = 0
    accepted_seeds = 0
    stopped_at = None
    for rank, index in enumerate(order):
        xs, ys = ix[index] + dx, iy[index] + dy
        in_grid = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        xs, ys = xs[in_grid], ys[in_grid]
        in_pref = mask[ys, xs]
        flat = ys[in_pref] * width + xs[in_pref]
        new = flat[~selected_flat[flat]]
        if n_selected + len(new) > budget_cells:
            stopped_at = int(rank)
            break
        selected_flat[new] = True
        n_selected += len(new)
        accepted_seeds += 1
    if n_selected != int(selected.sum()) or n_selected > budget_cells:
        raise ValueError("selection count or budget invariant failed")
    return selected, {"selected_cells": n_selected, "accepted_seeds": accepted_seeds,
                      "stopped_at_rank": stopped_at}


def evaluate_saved(score, positive, mask, *, size_m, expected_exact_capture):
    """Compare original fractional exact capture with discrete fixed-area rules."""
    score, positive = np.asarray(score), np.asarray(positive)
    iy, ix = np.nonzero(mask)
    n = len(ix)
    if score.shape != (n,) or positive.shape != (n,) or positive.dtype != bool or not np.isfinite(score).all():
        raise ValueError("saved scores and binary labels must align with the inside mask")
    n_positive = int(positive.sum())
    if not n_positive:
        raise ValueError("no positive cells")
    order = mt.rank_order(score, seed=0)
    original = mt.capture(order, positive, BUDGET_FRACTION)
    if abs(original - expected_exact_capture) > 1e-9:
        raise ValueError("saved B_env exact capture@5% did not reproduce")
    budget = int(np.floor(n * BUDGET_FRACTION))
    exact_sel = np.zeros(n, dtype=bool)
    exact_sel[order[:budget]] = True
    exact_captured = int(np.count_nonzero(exact_sel & positive))
    if abs(exact_captured / n_positive - original) > 1 / n_positive + 1e-12:
        raise ValueError("discrete exact capture disagrees with fractional reference")
    rows = [{"method": "exact", "radius_m": 0, "selected_cells": budget,
             "selected_fraction": budget / n, "captured_positive": exact_captured,
             "capture": exact_captured / n_positive, "accepted_seeds": budget,
             "stopped_at_rank": budget}]
    for radius in RADII_M:
        selected, meta = greedy_union(order, ix, iy, mask, radius_m=radius,
                                      size_m=size_m, budget_cells=budget)
        if meta["selected_cells"] > budget or np.any(selected[~mask]):
            raise ValueError("expanded selection exceeded budget or prefecture")
        captured = int(np.count_nonzero(selected[mask] & positive))
        rows.append({"method": f"seed_dilate_{radius}m", "radius_m": radius,
                     **meta, "selected_fraction": meta["selected_cells"] / n,
                     "captured_positive": captured, "capture": captured / n_positive,
                     "delta_vs_exact_discrete": captured / n_positive - exact_captured / n_positive})
    return {"n_cells": n, "n_positive": n_positive, "max_selected_cells": budget,
            "exact_fractional_reference_capture@5%": original,
            "exact_fractional_boundary_cell_weight": n * BUDGET_FRACTION - budget,
            "results": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    grid_path = args.art / "grid.json"
    mask_path = args.art / "grid_mask.npz"
    labels_path = args.art / "reports_by_year.npz"
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    if grid["crs"] != "EPSG:6678" or grid["size"] != 100:
        raise ValueError("expected existing 100 m EPSG:6678 grid")
    with np.load(mask_path) as file:
        mask = file["muni"] >= 0
    if mask.shape != (grid["ny"], grid["nx"]) or int(mask.sum()) != grid["cells_in_prefecture"]:
        raise ValueError("grid mask and metadata disagree")

    hashes = {name: prior.sha256(path) for name, path in
              (("grid.json", grid_path), ("grid_mask.npz", mask_path),
               ("reports_by_year.npz", labels_path))}
    results = {}
    with np.load(labels_path) as labels:
        for block, (year, stem) in prior.SPLITS.items():
            score_path = args.art / "eval" / f"{stem}_scores.npz"
            eval_path = args.art / "eval" / f"{stem}.json"
            reference = json.loads(eval_path.read_text(encoding="utf-8"))
            if reference["setup"]["test"] != year or reference["n_cells"] != int(mask.sum()):
                raise ValueError(f"{block} reference metadata does not match grid")
            with np.load(score_path) as scores:
                score = scores["B_env"]
            positive = labels[f"c{year}"][mask] > 0
            if int(positive.sum()) != reference["n_pos_cells"]:
                raise ValueError(f"{block} labels do not match reference")
            results[block] = {"test_year": year,
                              "test_label_period": "2026 April-September" if year == 2026 else "full fiscal year",
                              **evaluate_saved(score, positive, mask, size_m=grid["size"],
                                               expected_exact_capture=reference["B_env"]["capture@5%"])}
            hashes.update({f"eval/{stem}_scores.npz": prior.sha256(score_path),
                           f"eval/{stem}.json": prior.sha256(eval_path)})
            print(f"{block}: " + ", ".join(f"{row['radius_m']}m={row['capture']:.6f}"
                    f" ({row['selected_fraction']:.6%})" for row in results[block]["results"]), flush=True)

    result = {"mode": "descriptive diagnostic using saved B_env scores only",
              "question": "How does fixed-area seed dilation change capture relative to exact cells?",
              "definition": {"crs": grid["crs"], "cell_size_m": grid["size"],
                             "distance": "Euclidean centre-to-centre; prefecture-clipped disks",
                             "seed_order": "metrics.rank_order(saved B_env score,seed=0)",
                             "stop": "stop at first seed whose union would exceed floor(0.05 * inside cells); do not skip",
                             "budget_fraction": BUDGET_FRACTION, "radii_m": list(RADII_M)},
              "input_sha256": hashes,
              "implementation": {"script": "projects/_bear/akita-bear-risk-grid-100m/scripts/fixed_area_dilation.py",
                                 "script_sha256": prior.sha256(Path(__file__)),
                                 "metrics_sha256": prior.sha256(Path(mt.__file__)),
                                 "numpy": np.__version__},
              "years": results,
              "limitations": "This is a different spatial selection rule at equal-or-smaller area, not an estimate of reporting-coordinate error. It cannot isolate the fraction of low exact-cell capture caused by 100 m positional uncertainty. B3 labels cover April-September only; no retraining or model selection."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

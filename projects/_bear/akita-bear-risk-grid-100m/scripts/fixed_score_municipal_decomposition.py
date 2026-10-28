"""Decompose 2025→2026 Apr–Sep capture using one saved B2 B_env score surface.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/fixed_score_municipal_decomposition.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/_bear/akita-bear-risk-grid-100m \
      projects/_bear/akita-bear-risk-grid-100m/outputs/b2_fixed_score_municipal_decomposition.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

from grid import Grid
import labels as lb
import metrics as mt
import same_year_spatial_oof as spatial
from seasonal_transfer_b_env import seasonal_labels

YEARS = (2025, 2026)
AKITA_CITY = "05201"


def fixed_top_mask(scores):
    scores = np.asarray(scores)
    if scores.ndim != 1 or len(scores) == 0 or not np.isfinite(scores).all():
        raise ValueError("saved score must be a finite nonempty vector")
    order = mt.rank_order(scores, seed=0)
    n_top = int(np.ceil(.05 * len(scores)))
    top = np.zeros(len(scores), dtype=bool)
    top[order[:n_top]] = True
    return top


def audit_year(positive, top, muni, codes, names):
    positive, top, muni = map(np.asarray, (positive, top, muni))
    if positive.ndim != 1 or top.shape != positive.shape or muni.shape != positive.shape \
            or positive.dtype != bool or top.dtype != bool or len(codes) != len(names) \
            or np.any((muni < 0) | (muni >= len(codes))):
        raise ValueError("cell labels, fixed top set and municipality IDs must align")
    n = int(positive.sum())
    if n == 0:
        raise ValueError("target year has no positive cells")
    captured = positive & top
    rows = []
    for i, (code, name) in enumerate(zip(codes, names)):
        n_pos = int(np.count_nonzero(positive & (muni == i)))
        n_cap = int(np.count_nonzero(captured & (muni == i)))
        rows.append({"code5": code, "name": name, "n_positive": n_pos,
                     "positive_share": n_pos / n, "n_captured": n_cap,
                     "n_missed": n_pos - n_cap,
                     "recall": n_cap / n_pos if n_pos else None})
    n_cap = int(captured.sum())
    if sum(row["n_positive"] for row in rows) != n \
            or sum(row["n_captured"] for row in rows) != n_cap:
        raise ValueError("municipal sums do not reproduce prefecture totals")
    return {"n_positive": n, "n_captured": n_cap, "n_missed": n - n_cap,
            "capture": n_cap / n, "municipalities": rows}


def decompose(old, new):
    """Symmetric Kitagawa on common-support municipalities; leave zero cases unallocated."""
    a = {row["code5"]: row for row in old["municipalities"]}
    b = {row["code5"]: row for row in new["municipalities"]}
    if set(a) != set(b) or old["n_positive"] <= 0 or new["n_positive"] <= 0:
        raise ValueError("municipalities or positive totals differ")
    composition = within = unallocated = 0.0
    zeros, rows = [], []
    for code in a:
        first, second = a[code], b[code]
        p0, p1 = first["positive_share"], second["positive_share"]
        r0, r1 = first["recall"], second["recall"]
        direct_capture = second["n_captured"] / new["n_positive"] - first["n_captured"] / old["n_positive"]
        missed_change = ((second["n_positive"] - second["n_captured"]) / new["n_positive"]
                         - (first["n_positive"] - first["n_captured"]) / old["n_positive"])
        if first["n_positive"] == 0 or second["n_positive"] == 0:
            item = {"code5": code, "name": first["name"], "n_positive_2025": first["n_positive"],
                    "n_positive_2026": second["n_positive"],
                    "unallocated_direct_capture_change": direct_capture,
                    "missed_share_change": missed_change}
            zeros.append(item)
            comp_here = within_here = None
            unallocated += direct_capture
        else:
            comp_here = (p1 - p0) * (r1 + r0) / 2
            within_here = (r1 - r0) * (p1 + p0) / 2
            if not np.isclose(comp_here + within_here, direct_capture, atol=1e-12, rtol=0):
                raise ValueError(f"{code} Kitagawa identity failed")
            composition += comp_here
            within += within_here
        rows.append({"code5": code, "name": first["name"],
                     "direct_capture_change": direct_capture,
                     "composition_component": comp_here, "within_component": within_here,
                     "missed_share_change": missed_change})
    delta = new["capture"] - old["capture"]
    if not np.isclose(composition + within + unallocated, delta, atol=1e-12, rtol=0) \
            or not np.isclose(sum(row["missed_share_change"] for row in rows), -delta, atol=1e-12, rtol=0):
        raise ValueError("municipal decomposition does not reproduce overall capture difference")
    return {"delta_capture_2026_minus_2025": delta,
            "composition_component": composition, "within_component": within,
            "unallocated_zero_positive_component": unallocated,
            "composition_share_of_decline": composition / delta if delta < 0 else None,
            "zero_positive_municipalities": zeros,
            "municipal_contributions": rows}


def main():
    import duckdb
    import pyproj

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("output already exists; refusing post-result replacement")
    project = Path(__file__).resolve().parents[1]
    prior_path = project / "outputs/apr_sep_report_composition.json"
    score_audit_path = project / "outputs/b2_b3_false_negative_audit.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    score_audit = json.loads(score_audit_path.read_text(encoding="utf-8"))
    if prior["definition"]["source"] != lb.SIGHTING:
        raise ValueError("fixed source changed")
    fixed_files = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                   "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in fixed_files}
    if hashes != prior["setup"]["fixed_input_sha256"]:
        raise ValueError("fixed input artifact hashes differ")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if spatial.sha256(grid_path) != prior["setup"]["grid_json_sha256"] \
            or meta["crs"] != "EPSG:6678" or meta["size"] != 100:
        raise ValueError("fixed 100m municipality grid changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as masked:
        muni = masked["muni"]
    inside = muni >= 0
    if muni.shape != (grid.ny, grid.nx) or int(inside.sum()) != meta["cells_in_prefecture"]:
        raise ValueError("prefecture mask does not match grid metadata")
    with np.load(args.art / "reports_by_year.npz") as saved:
        known = {year: saved[f"c{year}"] for year in YEARS}
        full_2025 = saved["c2025"][inside] > 0
    score_path = args.art / "eval/b2_confirm_2023-2024_to_2025_scores.npz"
    eval_path = args.art / "eval/b2_confirm_2023-2024_to_2025.json"
    for path in (score_path, eval_path):
        name = f"eval/{path.name}"
        if spatial.sha256(path) != score_audit["input_sha256"][name]:
            raise ValueError(f"saved B2 score/evaluation provenance differs: {name}")
    reference = json.loads(eval_path.read_text(encoding="utf-8"))
    if reference["setup"]["train"] != [2023, 2024] or reference["setup"]["test"] != 2025 \
            or reference["n_cells"] != int(inside.sum()) \
            or int(full_2025.sum()) != reference["n_pos_cells"]:
        raise ValueError("saved B2 setup or full-year labels differ")
    with np.load(score_path) as saved_scores:
        scores = saved_scores["B_env"]
    if scores.shape != (int(inside.sum()),):
        raise ValueError("saved B2 score array does not match fixed prefecture cell order")
    baseline_capture = mt.capture(mt.rank_order(scores, seed=0), full_2025, .05)
    if not np.isclose(baseline_capture, reference["B_env"]["capture@5%"], atol=1e-9, rtol=0):
        raise ValueError("saved B2 full-fiscal-year capture@5% did not reproduce")
    top = fixed_top_mask(scores)

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2025-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known, years=YEARS)
    for year in YEARS:
        if info[year]["inside_window_reports"] != prior["years"][str(year)]["n_reports"] \
                or info[year]["outside_window_reports"] != prior["years"][str(year)]["n_outside_prefecture"] \
                or info[year]["positive_cells"] != prior["years"][str(year)]["n_positive_cells"]:
            raise ValueError(f"{year} seasonal labels do not match previous composition audit")
    municipality = muni[inside]
    years = {}
    for year in YEARS:
        positive = counts[year][inside] > 0
        audit = audit_year(positive, top, municipality, meta["codes"], meta["names"])
        prior_muni = {row["code5"]: row for row in prior["years"][str(year)]["municipalities"]}
        for row in audit["municipalities"]:
            if row["n_positive"] != prior_muni[row["code5"]]["positive_cell_count"]:
                raise ValueError(f"{year} {row['code5']} positive cell count differs from previous audit")
        years[str(year)] = audit
    breakdown = decompose(years["2025"], years["2026"])
    akita25 = next(row for row in years["2025"]["municipalities"] if row["code5"] == AKITA_CITY)
    akita26 = next(row for row in years["2026"]["municipalities"] if row["code5"] == AKITA_CITY)
    akita_delta = next(row for row in breakdown["municipal_contributions"] if row["code5"] == AKITA_CITY)
    increase_missed = -breakdown["delta_capture_2026_minus_2025"]
    result = {"mode": "descriptive decomposition on one saved B2 B_env score surface; no fitting",
              "definition": {"score": "B2 B_env saved scores, trained on fiscal 2023+2024, reused unchanged in both seasons",
                             "top5": "first ceil(0.05*n_prefecture_cells) in metrics.rank_order(score,seed=0), identical for both years",
                             "capture": "captured positive integer cells / all Apr–Sep positive cells; unlike fractional-boundary legacy capture",
                             "municipality": "existing grid_mask.npz cell-centre assignment",
                             "kitagawa": "on municipalities positive in both years: sum((p26-p25)*(r26+r25)/2) + sum((r26-r25)*(p26+p25)/2)",
                             "zero_positive": "undefined recall never imputed; direct capture contribution left unallocated",
                             "missed_share_change": "(n26-h26)/N26 - (n25-h25)/N25; avoids incomparable raw counts"},
              "setup": {"source": lb.SIGHTING, "grid_json_sha256": spatial.sha256(grid_path),
                        "fixed_input_sha256": hashes, "b2_score_npz_sha256": spatial.sha256(score_path),
                        "b2_eval_json_sha256": spatial.sha256(eval_path),
                        "prior_composition_json_sha256": spatial.sha256(prior_path),
                        "prior_score_audit_json_sha256": spatial.sha256(score_audit_path),
                        "n_prefecture_cells": int(inside.sum()), "n_selected_top5_cells": int(top.sum()),
                        "b2_full_fiscal_year_fractional_capture_reproduced": baseline_capture},
              "labels": info, "years": years, "decomposition": breakdown,
              "akita_city": {"2025": akita25, "2026": akita26,
                             "missed_share_change": akita_delta["missed_share_change"],
                             "share_of_prefecture_missed_share_increase":
                                 akita_delta["missed_share_change"] / increase_missed if increase_missed > 0 else None,
                             "capture_composition_component": akita_delta["composition_component"],
                             "capture_within_component": akita_delta["within_component"]},
              "limitations": ["fixed B2 score is not refit or calibrated to the seasonal labels",
                              "municipal Kitagawa terms are descriptive, not causal effects",
                              "reporting effort, location precision and bear behaviour can change across years"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("capture:", years["2025"]["capture"], years["2026"]["capture"], flush=True)
    print("decomposition:", {k: v for k, v in breakdown.items() if k != "municipal_contributions"}, flush=True)
    print("Akita city:", result["akita_city"], flush=True)


if __name__ == "__main__":
    main()

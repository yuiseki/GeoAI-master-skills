"""Describe existing B_env static features among captured and missed positives.

Run from the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/positive_feature_audit.py ART_DIR OUT_JSON

Uses saved B2/B3 scores and labels, and reconstructs only the existing static
features from their stored arrays. No model fitting or new feature definition.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import ks_2samp, mannwhitneyu

import false_negative_audit as previous
import features as ft
import metrics as mt


def feature_unit(name):
    cover = {"tree", "crop", "built", "grass", "water"}
    if name in cover:
        return "fraction of valid WorldCover pixels in 100m cell"
    if name.split("_")[0] in cover:
        return "mean 100m-cell fraction in square window"
    if name in {"forest_edge", "elev", "tpi_500"} or name.startswith("d_"):
        return "m"
    if name == "slope":
        return "degrees"
    if name.startswith("pop_"):
        return "estimated persons in square window"
    if name == "bldg_500":
        return "OSM building centroids in square window"
    raise ValueError(f"unknown B_env feature: {name}")


def _describe(values):
    values = np.asarray(values, dtype=float)
    valid = values[np.isfinite(values)]
    info = {"n_total": int(len(values)), "n_valid": int(len(valid)),
            "n_missing": int(len(values) - len(valid))}
    if len(valid):
        q1, med, q3 = np.quantile(valid, [0.25, 0.5, 0.75])
        info.update({"q25": float(q1), "median": float(med), "q75": float(q3),
                     "iqr": float(q3 - q1)})
    else:
        info.update({"q25": None, "median": None, "q75": None, "iqr": None})
    return info, valid


def summarize_feature(captured_values, missed_values):
    """Compare finite values only, retaining both groups' missing counts."""
    cap, cap_valid = _describe(captured_values)
    miss, miss_valid = _describe(missed_values)
    out = {"captured": cap, "missed": miss,
           "captured_minus_missed_median": None,
           "captured_minus_missed_iqr": None,
           "ks_statistic": None, "cliffs_delta": None}
    if len(cap_valid) and len(miss_valid):
        out["captured_minus_missed_median"] = cap["median"] - miss["median"]
        out["captured_minus_missed_iqr"] = cap["iqr"] - miss["iqr"]
        out["ks_statistic"] = float(ks_2samp(cap_valid, miss_valid, method="asymp").statistic)
        u = float(mannwhitneyu(cap_valid, miss_valid, alternative="two-sided",
                               method="asymptotic").statistic)
        out["cliffs_delta"] = float(2 * u / (len(cap_valid) * len(miss_valid)) - 1)
    return out


def audit_year(score, positive, features, *, expected_capture, expected_captured, expected_missed):
    score, positive = np.asarray(score), np.asarray(positive)
    n = len(score)
    if score.ndim != 1 or positive.shape != (n,) or positive.dtype != bool \
            or not np.isfinite(score).all() or not features:
        raise ValueError("scores, binary labels and features must be aligned and valid")
    for name, arr in features.items():
        if np.asarray(arr).shape != (n,):
            raise ValueError(f"feature {name} is not aligned with saved scores")
    order = mt.rank_order(score, seed=0)
    capture = mt.capture(order, positive, 0.05)
    if abs(capture - expected_capture) > 1e-9:
        raise ValueError("saved B_env capture@5% did not reproduce")
    n_top = int(np.ceil(0.05 * n))
    top = np.zeros(n, dtype=bool)
    top[order[:n_top]] = True
    captured = positive & top
    missed = positive & ~top
    n_cap, n_miss = int(captured.sum()), int(missed.sum())
    if n_cap != expected_captured or n_miss != expected_missed \
            or abs(n_cap / (n_cap + n_miss) - capture) > 1 / (n_cap + n_miss) + 1e-12:
        raise ValueError("captured/missed counts differ from prior audit")
    summaries = {name: summarize_feature(arr[captured], arr[missed])
                 for name, arr in features.items()}
    return {"n_cells": n, "n_top5_cells": n_top, "n_positive": n_cap + n_miss,
            "n_captured_positive": n_cap, "n_missed_positive": n_miss,
            "capture_at_5_from_saved_scores": capture, "features": summaries}


def rank_consistent(years):
    """Rank same-direction features by the weaker year's absolute Cliff effect."""
    b2, b3 = years["B2"]["features"], years["B3"]["features"]
    if set(b2) != set(b3):
        raise ValueError("B2/B3 feature sets differ")
    rows = []
    for name in b2:
        a, b = b2[name]["cliffs_delta"], b3[name]["cliffs_delta"]
        if a is None or b is None or a == 0 or b == 0 or (a > 0) != (b > 0):
            continue
        rows.append({"feature": name, "direction": "captured_higher" if a > 0 else "captured_lower",
                     "B2_cliffs_delta": a, "B3_cliffs_delta": b,
                     "min_abs_cliffs_delta": min(abs(a), abs(b)),
                     "B2_ks_statistic": b2[name].get("ks_statistic"),
                     "B3_ks_statistic": b3[name].get("ks_statistic")})
    return sorted(rows, key=lambda row: (-row["min_abs_cliffs_delta"], row["feature"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()

    project = Path(__file__).resolve().parents[1]
    prior_path = project / "outputs/b2_b3_false_negative_audit.json"
    b1_path = project / "outputs/b1_poisson_target_isolation.json"
    prior_audit = json.loads(prior_path.read_text(encoding="utf-8"))
    b1 = json.loads(b1_path.read_text(encoding="utf-8"))
    names = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
             "reports_by_year.npz", "grid_mask.npz")
    hashes = {name: previous.sha256(args.art / name) for name in names}
    if hashes != b1["setup"]["input_sha256"]:
        raise ValueError("static feature or label inputs differ from B1 provenance")
    for name in ("grid_mask.npz", "reports_by_year.npz"):
        if hashes[name] != prior_audit["input_sha256"][name]:
            raise ValueError("prior audit input differs")

    with np.load(args.art / "grid_mask.npz") as grid:
        inside = grid["muni"] >= 0
    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    if list(static) != b1["setup"]["feature_names"] or len(static) != 28:
        raise ValueError("B_env static feature names differ from existing model")
    values = {name: arr[inside] for name, arr in static.items()}
    del static

    years = {}
    with np.load(args.art / "reports_by_year.npz") as labels:
        for block, (year, stem) in previous.SPLITS.items():
            score_path = args.art / "eval" / f"{stem}_scores.npz"
            eval_path = args.art / "eval" / f"{stem}.json"
            ref = json.loads(eval_path.read_text(encoding="utf-8"))
            if ref["setup"]["test"] != year or ref["n_cells"] != int(inside.sum()):
                raise ValueError(f"{block} reference metadata differs")
            with np.load(score_path) as scores:
                score = scores["B_env"]
            positive = labels[f"c{year}"][inside] > 0
            prior_year = prior_audit["years"][block]
            if int(positive.sum()) != ref["n_pos_cells"] or prior_year["test_year"] != year:
                raise ValueError(f"{block} labels or prior audit differ")
            hashes[f"eval/{stem}_scores.npz"] = previous.sha256(score_path)
            hashes[f"eval/{stem}.json"] = previous.sha256(eval_path)
            for name in (f"eval/{stem}_scores.npz", f"eval/{stem}.json"):
                if hashes[name] != prior_audit["input_sha256"][name]:
                    raise ValueError(f"{block} saved-score provenance differs")
            years[block] = {"test_year": year,
                            "test_label_period": "2026 April-September" if year == 2026 else "full fiscal year",
                            **audit_year(score, positive, values,
                                         expected_capture=ref["B_env"]["capture@5%"],
                                         expected_captured=prior_year["n_captured_positive"],
                                         expected_missed=prior_year["n_missed_positive"])}
            for name, entry in years[block]["features"].items():
                entry["unit"] = feature_unit(name)
            print(f"{block}: {years[block]['n_captured_positive']} captured,"
                  f" {years[block]['n_missed_positive']} missed; {len(values)} features", flush=True)

    ranked = rank_consistent(years)
    result = {"mode": "descriptive diagnostic; no fitting or model selection",
              "question": "How do existing B_env static features differ between captured and missed positives?",
              "definition": {"positive": "at least one report in test period",
                             "captured": "positive among first ceil(0.05*n) cells in metrics.rank_order(saved B_env score,seed=0)",
                             "missed": "positive outside that set",
                             "quantiles": "finite values only; NaN/inf counted as missing, never imputed",
                             "difference": "captured minus missed",
                             "cliffs_delta": "2*mannwhitney_U/(n_captured_valid*n_missed_valid)-1",
                             "consistent_rank": "same nonzero Cliff sign in B2 and B3, ordered by min(abs(delta_B2),abs(delta_B3))",
                             "top_display_count": 5},
              "feature_notes": {"landcover": "WorldCover 2021 cell fractions; _500/_1500 are square-window means of cell fractions, not circular cover shares",
                                "forest_edge": "negative inside >=50% tree cell, positive outside, metres to nearest boundary cell",
                                "pop_500/pop_2000": "WorldPop 2020 estimated persons summed in 11x11 / 41x41 cells",
                                "bldg_500": "OSM snapshot building centroids summed in 11x11 cells",
                                "osm_distances": "Euclidean cell-centre distances to mapped OSM features, not walking distance",
                                "elev/slope/tpi_500": "GSI DEM elevation m, slope degrees, elevation minus 11x11 valid-cell mean m"},
              "input_sha256": hashes,
              "implementation": {"script": "projects/_bear/akita-bear-risk-grid-100m/scripts/positive_feature_audit.py",
                                 "script_sha256": previous.sha256(Path(__file__)),
                                 "features_py_sha256": previous.sha256(Path(ft.__file__)),
                                 "metrics_py_sha256": previous.sha256(Path(mt.__file__)),
                                 "numpy": np.__version__, "scipy": scipy.__version__},
              "years": years, "same_direction_ranked_features": ranked,
              "limitations": "Selection is determined by model scores derived from these same features, so group differences do not establish causal drivers or feature importance. B2/B3 share cells; no independent replication. Correlated features, observation bias, and 2026 partial-year labels remain. No p-values or multiple-test claims."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ranked[:5], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

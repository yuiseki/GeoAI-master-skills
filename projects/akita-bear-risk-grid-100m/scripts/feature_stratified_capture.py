"""Describe saved B_env B2/B3 top-5% capture in fixed feature quintile strata.

Run from repository root:
    uvx --with numpy --with scipy python \
      projects/akita-bear-risk-grid-100m/scripts/feature_stratified_capture.py ART_DIR OUT_JSON
No fitting, score modification, new feature, or alternate threshold is performed.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import false_negative_audit as previous
import features as ft
import metrics as mt
from positive_feature_audit import feature_unit


FEATURES = ("d_road_major", "d_road", "d_building", "crop", "bldg_500")
ATTENTION = {"d_road_major": "Q5", "d_road": "Q5", "d_building": "Q5",
             "crop": "Q5", "bldg_500": "Q1"}


def quintile_strata(values):
    """Whole-grid value cutpoints; a tied boundary goes to the lower stratum."""
    values = np.asarray(values)
    if values.ndim != 1 or not np.issubdtype(values.dtype, np.number):
        raise ValueError("feature values must be numeric and aligned 1-D")
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError("feature has no finite cells")
    cuts = np.quantile(values[finite], [0.2, 0.4, 0.6, 0.8])
    strata = np.full(len(values), -1, dtype=np.int8)
    strata[finite] = np.searchsorted(cuts, values[finite], side="left")
    return cuts, strata


def audit_year(score, positive, features, *, expected_capture, expected_captured, expected_missed):
    score, positive = np.asarray(score), np.asarray(positive)
    n = len(score)
    if score.ndim != 1 or positive.shape != (n,) or positive.dtype != bool \
            or n == 0 or not np.isfinite(score).all():
        raise ValueError("scores and binary labels must be aligned and valid")
    for name, values in features.items():
        if np.asarray(values).shape != (n,):
            raise ValueError(f"feature {name} must be aligned with saved scores")
    order = mt.rank_order(score, seed=0)
    capture = mt.capture(order, positive, 0.05)
    if abs(capture - expected_capture) > 1e-9:
        raise ValueError("saved B_env capture@5% did not reproduce")
    n_top = int(np.ceil(0.05 * n))
    top = np.zeros(n, dtype=bool)
    top[order[:n_top]] = True
    captured = positive & top
    n_positive, n_captured = int(positive.sum()), int(captured.sum())
    if n_positive == 0 or n_captured != expected_captured \
            or n_positive - n_captured != expected_missed \
            or abs(n_captured / n_positive - capture) > 1 / n_positive + 1e-12:
        raise ValueError("binary top-5% membership differs from prior audit")

    out_features = {}
    for name, values in features.items():
        cuts, strata = quintile_strata(values)
        rows = []
        for j in (*range(5), -1):
            in_stratum = strata == j
            n_cells = int(in_stratum.sum())
            n_pos = int(np.count_nonzero(in_stratum & positive))
            n_cap = int(np.count_nonzero(in_stratum & captured))
            rows.append({"stratum": f"Q{j + 1}" if j >= 0 else "missing",
                         "n_cells": n_cells, "n_positive": n_pos,
                         "n_captured_positive": n_cap,
                         "recall": n_cap / n_pos if n_pos else None,
                         "share_of_all_positives": n_pos / n_positive})
        if sum(r["n_cells"] for r in rows) != n \
                or sum(r["n_positive"] for r in rows) != n_positive \
                or sum(r["n_captured_positive"] for r in rows) != n_captured:
            raise ValueError(f"{name}: strata do not partition all cells and positives")
        out_features[name] = {"unit": feature_unit(name),
                              "cutpoints_q20_q40_q60_q80": cuts.tolist(),
                              "strata": rows}
    return {"n_cells": n, "n_top5_cells": n_top, "n_positive": n_positive,
            "n_captured_positive": n_captured, "n_missed_positive": n_positive - n_captured,
            "overall_recall": n_captured / n_positive,
            "reference_fractional_capture_at_5": capture, "features": out_features}


def consistent_low(years, name, stratum):
    """Predeclared stratum is below overall recall in both periods, if defined."""
    for year in ("B2", "B3"):
        row = next(r for r in years[year]["features"][name]["strata"]
                   if r["stratum"] == stratum)
        if row["n_positive"] == 0 or row["recall"] >= years[year]["overall_recall"]:
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    project = Path(__file__).resolve().parents[1]
    prior = json.loads((project / "outputs/b2_b3_false_negative_audit.json").read_text(encoding="utf-8"))
    b1 = json.loads((project / "outputs/b1_poisson_target_isolation.json").read_text(encoding="utf-8"))
    input_names = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
                   "reports_by_year.npz", "grid_mask.npz")
    hashes = {name: previous.sha256(args.art / name) for name in input_names}
    if hashes != b1["setup"]["input_sha256"]:
        raise ValueError("input feature/label artifacts differ from B1 provenance")
    with np.load(args.art / "grid_mask.npz") as grid:
        inside = grid["muni"] >= 0
    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    if list(static) != b1["setup"]["feature_names"] or len(static) != 28:
        raise ValueError("existing B_env feature definitions differ")
    values = {name: static[name][inside] for name in FEATURES}
    del static

    years = {}
    with np.load(args.art / "reports_by_year.npz") as labels:
        for block, (year, stem) in previous.SPLITS.items():
            score_path = args.art / "eval" / f"{stem}_scores.npz"
            eval_path = args.art / "eval" / f"{stem}.json"
            ref = json.loads(eval_path.read_text(encoding="utf-8"))
            if ref["setup"]["test"] != year or ref["n_cells"] != int(inside.sum()):
                raise ValueError(f"{block} saved evaluation metadata differs")
            with np.load(score_path) as scores:
                score = scores["B_env"]
            positive = labels[f"c{year}"][inside] > 0
            if int(positive.sum()) != ref["n_pos_cells"]:
                raise ValueError(f"{block} labels differ from saved evaluation")
            for name, path in ((f"eval/{stem}_scores.npz", score_path),
                               (f"eval/{stem}.json", eval_path)):
                hashes[name] = previous.sha256(path)
                if hashes[name] != prior["input_sha256"][name]:
                    raise ValueError(f"{block} saved score provenance differs")
            prior_year = prior["years"][block]
            years[block] = {"test_year": year,
                            "test_label_period": "April-September" if year == 2026 else "full fiscal year",
                            **audit_year(score, positive, values,
                                         expected_capture=ref["B_env"]["capture@5%"],
                                         expected_captured=prior_year["n_captured_positive"],
                                         expected_missed=prior_year["n_missed_positive"])}
    for name in FEATURES:
        if years["B2"]["features"][name]["cutpoints_q20_q40_q60_q80"] \
                != years["B3"]["features"][name]["cutpoints_q20_q40_q60_q80"]:
            raise ValueError(f"{name}: strata boundaries changed between years")
    attention = {name: {"stratum": stratum,
                        "lower_than_overall_in_both_years": consistent_low(years, name, stratum)}
                 for name, stratum in ATTENTION.items()}
    result = {"mode": "exploratory descriptive diagnostic; no fitting or score changes",
              "question": "Which preselected B_env feature strata have low top-5% recall in B2/B3?",
              "definition": {"strata": "fixed whole-prefecture finite-value quintile cutpoints; exact ties assigned to lower stratum; empty nominal strata retained; missing separate",
                             "top5": "first ceil(0.05*n) cells from metrics.rank_order(saved B_env score,seed=0)",
                             "recall": "captured positive cells / all positive cells in stratum",
                             "share_of_all_positives": "positive cells in stratum / all prefecture positive cells",
                             "attention_rule": "Q5 for distances and crop, Q1 for bldg_500; lower than overall recall in both B2/B3 with nonzero positives"},
              "input_sha256": hashes,
              "implementation": {"script": "projects/akita-bear-risk-grid-100m/scripts/feature_stratified_capture.py",
                                 "script_sha256": previous.sha256(Path(__file__)),
                                 "features_py_sha256": previous.sha256(Path(ft.__file__)),
                                 "metrics_py_sha256": previous.sha256(Path(mt.__file__)),
                                 "numpy": np.__version__},
              "years": years, "attention_strata": attention,
              "limitations": "Features were selected after a prior B2/B3 outcome audit. Strata use model inputs and do not identify causal drivers; B2/B3 share grid cells and are not independent replication. Low recall can reflect score selection, correlated features, reporting bias, or data vintage. B3 has April-September labels only."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overall_recall": {k: years[k]["overall_recall"] for k in years},
                      "attention_strata": attention}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

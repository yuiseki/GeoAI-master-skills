"""B2: development period (EXPERIMENT_PLAN.md). Uses only target years 1990-1999 and ranks up to 1999; nothing is
chosen. Scores every model in A, B and C (exploratory), then freezes the specification (coverage rule, features,
models, metric, splits) with its sha256 in outputs/b2_frozen_spec.json. Stops if that file exists.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj python \
      projects/_bear/beech-masting-satellite-proxy/scripts/run_dev.py projects/_bear/beech-masting-satellite-proxy/outputs
"""

import argparse
import hashlib
import json
from pathlib import Path

import model as M
import rows as R

DEV = list(range(1990, 2000))
MODELS = list(M.FEATURES)


def summarise(ev):
    return {"scores": ev["scores"], "within_by_year": {m: w["by_year"] for m, w in ev["within"].items()},
            "years_dropped": {m: w["years_dropped"] for m, w in ev["within"].items()}}


def same_splits(sites):
    """The folds must be those of beech-masting-spatial-proxy (its outputs/splits_audit.json)."""
    prev = json.loads((R.CLIMATE.parent / "splits_audit.json").read_text(encoding="utf-8"))["folds"]
    now = [{"repeat": r, "fold": f, "test_sites": len(te), "train_sites": len(tr),
            "buffer_left_out": len(sites) - len(te) - len(tr)}
           for r in range(M.REPEATS) for f, (te, tr) in enumerate(M.spatial_folds(sites, r))]
    if now != prev:
        raise SystemExit("the folds differ from beech-masting-spatial-proxy")
    print("folds identical to beech-masting-spatial-proxy:", len(now), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    spec_path = a.outputs / "b2_frozen_spec.json"
    if spec_path.exists():
        raise SystemExit(f"{spec_path} exists: the specification is frozen")
    rule = json.loads((a.outputs / "coverage_rule.json").read_text(encoding="utf-8"))
    rows, ranks, sites, raw, prov = R.load(a.outputs, max_rank_year=1999)
    rows = rows[rows.t.isin(DEV)]
    assert rows.t.max() <= 1999 and ranks.year.max() <= 1999
    same_splits(sites)
    raw_dev = raw[raw.t.isin(DEV)]
    k = rule["min_years"]
    res = {"A": summarise(M.evaluate(M.run_A(rows, raw_dev, DEV, DEV, MODELS, k), MODELS)),
           "B": summarise(M.evaluate(M.run_BC(rows, raw_dev, ranks, sites, "B", DEV, DEV, MODELS, k), MODELS)),
           "C": summarise(M.evaluate(M.run_BC(rows, raw_dev, ranks, sites, "C", DEV, DEV, MODELS, k), MODELS))}
    for s, r in res.items():
        print(s, {m: (v["n"], round(v["within_year_spearman"], 3), round(v["rmse"], 3)) for m, v in r["scores"].items()},
              flush=True)
    (a.outputs / "b2_dev_scores.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    spec = {"coverage_rule": rule, "models": M.FEATURES, "satellite_features": M.SAT,
            "anomaly": "site mean over the fold's training years (A, C: without t and t + 1; B: leave own year out)",
            "primary": "scheme C, within-year Spearman, repeat-mean predictions, years with >= 10 rows, equal weights",
            "gate": "S2 - B0: point > 0 and 90% year-bootstrap lower bound > 0",
            "splits": {"block_m": M.BLOCK_M, "buffer_m": M.BUFFER_M, "folds": M.FOLDS, "repeats": M.REPEATS,
                       "k_near": M.K_NEAR},
            "inputs": prov, "dev_targets": [DEV[0], DEV[-1]], "chosen": "nothing (all fixed in the plan)"}
    body = json.dumps(spec, indent=1) + "\n"
    spec_path.write_text(body, encoding="utf-8")
    print("sha256", hashlib.sha256(body.encode()).hexdigest())


if __name__ == "__main__":
    main()

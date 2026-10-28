"""B3 (decisive) on the confirmation years t = 2000-2008, once, with the specification frozen in
outputs/b2_frozen_spec.json (EXPERIMENT_PLAN.md). Coefficients and climatologies are refitted in each fold;
training may use every target year 1990-2008 allowed by the scheme.

Writes outputs/b3_confirm.json and the predictions to ART/confirm_predictions.parquet. Stops if the specification
is missing or the output exists.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python \
      projects/beech-masting-satellite-proxy/scripts/run_confirm.py projects/beech-masting-satellite-proxy/outputs \
      artifacts/beech-masting-satellite-proxy
"""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import model as M
import rows as R

CONF = list(range(2000, 2009))
ALL = list(range(1990, 2009))
MODELS = list(M.FEATURES)
CLAIMS = {"H": ("S2", "B0"), "H-ps": ("S1", "B0"), "H-cs": ("S2", "S1"), "R-vs-R0": ("RS2", "R0")}


def claims(within):
    by = {m: w["by_year"] for m, w in within.items()}
    out = {}
    for c, (cand, comp) in CLAIMS.items():
        out[c] = {"cand": cand, "comp": comp, **M.diff_bootstrap(by[cand], by[comp])}
        out[c]["verdict"] = M.rule(out[c])
    lvl = M.diff_bootstrap(by["RS2"], {t: 0.0 for t in by["RS2"]})
    out["R-level"] = {"cand": "RS2", "comp": "0", **lvl, "verdict": M.rule(lvl)}
    out["R"] = {"verdict": "supported" if out["R-level"]["verdict"] == out["R-vs-R0"]["verdict"] == "supported"
                else "not supported"}
    return out


def load_spec(outputs):
    p = outputs / "b2_frozen_spec.json"
    if not p.exists():
        raise SystemExit("B2 has not frozen the specification")
    body = p.read_text(encoding="utf-8")
    return json.loads(body), hashlib.sha256(body.encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    spec, spec_sha = load_spec(a.outputs)
    out_path = a.outputs / "b3_confirm.json"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists: the confirmation has been run")
    rows, ranks, sites, raw, prov = R.load(a.outputs)
    if prov != spec["inputs"]:
        raise SystemExit(f"inputs differ from the frozen specification: {prov}")
    k = spec["coverage_rule"]["min_years"]
    pred = {"A": M.run_A(rows, raw, CONF, ALL, MODELS, k),
            "B": M.run_BC(rows, raw, ranks, sites, "B", CONF, ALL, MODELS, k),
            "C": M.run_BC(rows, raw, ranks, sites, "C", CONF, ALL, MODELS, k)}
    a.art.mkdir(parents=True, exist_ok=True)
    pd.concat([p.assign(scheme=s) for s, p in pred.items()]).to_parquet(a.art / "confirm_predictions.parquet",
                                                                        index=False)
    res = {"spec_sha256": spec_sha, "confirm_targets": [CONF[0], CONF[-1]], "schemes": {}}
    for s, p in pred.items():
        ev = M.evaluate(p, MODELS)
        res["schemes"][s] = {"scores": ev["scores"],
                             "within_by_year": {m: w["by_year"] for m, w in ev["within"].items()},
                             "years_dropped": {m: w["years_dropped"] for m, w in ev["within"].items()},
                             "rows_by_year": ev["rows"][ev["rows"].model == "S2"].groupby("t").size().to_dict(),
                             "claims": claims(ev["within"])}
    res["gate"] = {"claim": "H", "scheme": "C", **res["schemes"]["C"]["claims"]["H"]}
    res["gate"]["label"] = ("satellite spatial signal supported" if res["gate"]["verdict"] == "supported"
                            else "satellite spatial signal not supported")
    out_path.write_text(json.dumps(res, indent=1, default=int) + "\n", encoding="utf-8")
    for s, r in res["schemes"].items():
        print(s, {m: (v["n"], round(v["within_year_spearman"], 3), round(v["rmse"], 3)) for m, v in r["scores"].items()})
        print("  ", {c: (round(v.get("diff", float("nan")), 3), round(v.get("lo90", float("nan")), 3), v["verdict"])
                     for c, v in r["claims"].items()})
    print(res["gate"]["label"])


if __name__ == "__main__":
    main()

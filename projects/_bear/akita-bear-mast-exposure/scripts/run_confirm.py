"""B2, B3: the confirmation, once. Checks the frozen specification's sha256, fits M1-M5 (retrospective) and M5
(operational) on the training years of each target, scores 2025 and 2026 (April-September) against M0 = B_env,
with the 10 km block bootstrap. Stops if the output exists.

    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-mast-exposure/scripts \
      uvx --with numpy --with pandas --with pyarrow --with scikit-learn python run_confirm.py BEAR_ART ART MAST_CSV OUTDIR
"""

import json
import os
import sys

import numpy as np

import data
import evaluate as ev
import metrics as mt

SPEC_SHA = "655c8590c4bcdf72d46c10c0e06fcf3ab70a7b45b717a9da0d24007407c0a643"


def judge(d25, d26):
    ok = [d["diff"] > 0 and d["lo90"] > 0 for d in (d25, d26)]
    return "supported" if all(ok) else ("mixed / not confirmed" if any(ok) else "not supported")


def main():
    bear, art, mast_csv, outdir = sys.argv[1:5]
    out = f"{outdir}/b3_confirm.json"
    if os.path.exists(out):
        raise SystemExit(f"{out} exists; the confirmation runs once")
    spec_path = f"{outdir}/b1_frozen_spec.json"
    if data.sha256(spec_path) != SPEC_SHA:
        raise SystemExit("the frozen specification changed")
    spec = json.load(open(spec_path))
    d = data.load(bear, art)
    s = {"retrospective": data.read_mast(mast_csv, "fruiting"), "operational": data.read_mast(mast_csv, "flowering")}
    res = {"spec_sha256": SPEC_SHA, "radius_m": spec["radius_m"], "targets": {}}
    scores = {}
    boots = {}
    for target in (2025, 2026):
        benv, c = d["benv"][target], d["counts"][target]
        r = {"train": data.TRAIN[target], "surface": data.SURFACE[target], "M0": ev.metrics(benv, c), "retrospective": {}, "operational": {}}
        for variant, models in (("retrospective", ev.MODELS), ("operational", {"M5": "beech_oak"})):
            for m, cat in models.items():
                e, _ = data.exposure_vec(d["exposure"], spec["features"][m], d["muni"])
                o = ev.run(benv, e, s[variant], d["counts"], data.TRAIN[target], target)
                rr = {"fit": o["fit"], "s_target": o["s_target"], "beta_times_s_target": o["beta_times_s_target"], "metrics": o["metrics"]}
                rr["diff_capture@5%"] = ev.diff(o["score"], benv, c, d["blocks"])
                if m == "M5":
                    rr["diff_capture@10%"] = ev.diff(o["score"], benv, c, d["blocks"], k=0.10)
                    rr["diff_capture@5%_reports"] = ev.diff(o["score"], benv, c, d["blocks"], weights_counts=True)
                if variant == "retrospective" and m == "M5":
                    oa, ob = mt.rank_order(o["score"]), mt.rank_order(benv)
                    boots[target] = mt.bootstrap_diff(oa, ob, c > 0, d["blocks"], 0.05, B=1000, seed=0)[2]
                scores[f"{target}_{variant}_{m}"] = o["score"].astype(np.float32)
                r[variant][m] = rr
                print(target, variant, m, round(rr["metrics"]["capture@5%"], 5), rr["diff_capture@5%"], round(o["fit"]["beta"], 4), flush=True)
        res["targets"][target] = r
    pooled = (boots[2025] + boots[2026]) / 2  # the same block draws in both years (same blocks, same seed)
    p = np.mean([res["targets"][t]["retrospective"]["M5"]["diff_capture@5%"]["diff"] for t in (2025, 2026)])
    res["pooled_M5_diff_capture@5%_supplementary"] = {"diff": float(p), "lo90": float(np.quantile(pooled, 0.05)), "hi90": float(np.quantile(pooled, 0.95))}
    res["H"] = {"rule": spec["rule"], "verdict": judge(res["targets"][2025]["retrospective"]["M5"]["diff_capture@5%"],
                                                    res["targets"][2026]["retrospective"]["M5"]["diff_capture@5%"])}
    res["operational_M5"] = {"verdict_same_rule": judge(res["targets"][2025]["operational"]["M5"]["diff_capture@5%"],
                                                       res["targets"][2026]["operational"]["M5"]["diff_capture@5%"])}
    json.dump(res, open(out, "w"), indent=1)
    np.savez_compressed(f"{art}/b3_confirm_scores.npz", **scores)
    print(json.dumps({"H": res["H"], "operational": res["operational_M5"], "pooled": res["pooled_M5_diff_capture@5%_supplementary"]}, indent=1))


if __name__ == "__main__":
    main()

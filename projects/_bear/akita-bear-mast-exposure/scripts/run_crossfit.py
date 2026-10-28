"""X2: beta refitted with the cross-fit B_env offsets of the training years; the targets are scored with the
existing B2/B3 surfaces, as in run_confirm.py. Stops if the output exists.

    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-mast-exposure/scripts \
      uvx --with numpy --with pandas --with pyarrow --with scikit-learn python run_crossfit.py BEAR_ART ART MAST_CSV OUTDIR
"""

import json
import os
import sys

import numpy as np

import crossfit as cf
import data
import evaluate as ev
import model
from run_confirm import SPEC_SHA


def main():
    bear, art, mast_csv, outdir = sys.argv[1:5]
    out = f"{outdir}/x2_crossfit_beta.json"
    if os.path.exists(out):
        raise SystemExit(f"{out} exists")
    if data.sha256(f"{outdir}/b1_frozen_spec.json") != SPEC_SHA:
        raise SystemExit("the frozen specification changed")
    spec = json.load(open(f"{outdir}/b1_frozen_spec.json"))
    orig = json.load(open(f"{outdir}/b3_confirm.json"))
    d = data.load(bear, art)
    oof = np.load(f"{art}/crossfit_benv_scores.npz")
    e, _ = data.exposure_vec(d["exposure"], spec["features"]["M5"], d["muni"])
    s = {"retrospective": data.read_mast(mast_csv, "fruiting"), "operational": data.read_mast(mast_csv, "flowering")}
    res = {"spec_sha256": SPEC_SHA, "feature": spec["features"]["M5"], "targets": {}}
    for target, years in cf.OOF.items():
        benv, c = d["benv"][target], d["counts"][target]
        r = {"train": cf.BETA_YEARS[target], "offsets": {y: cf.key(tr) for y, tr in years.items()}, "surface": data.SURFACE[target]}
        for variant in ("retrospective", "operational"):
            sv = s[variant]
            fit = model.fit([(model.logit(oof[cf.key(years[y])].astype(float)), sv[y] * e, d["counts"][y] > 0) for y in cf.BETA_YEARS[target]])
            sc = model.score(benv, e, fit["beta"], sv[target])
            o = orig["targets"][str(target)][variant]["M5"]
            r[variant] = {
                "cross_fit": {"fit": fit, "beta_times_s_target": fit["beta"] * sv[target], "metrics": ev.metrics(sc, c),
                              "diff_capture@5%": ev.diff(sc, benv, c, d["blocks"]),
                              "diff_capture@10%": ev.diff(sc, benv, c, d["blocks"], k=0.10),
                              "diff_capture@5%_reports": ev.diff(sc, benv, c, d["blocks"], weights_counts=True)},
                "in_sample_original": {"fit": o["fit"], "beta_times_s_target": o["beta_times_s_target"],
                                       "diff_capture@5%": o["diff_capture@5%"], "diff_capture@10%": o["diff_capture@10%"],
                                       "diff_capture@5%_reports": o["diff_capture@5%_reports"]},
                "s_target": sv[target]}
            x = r[variant]["cross_fit"]
            print(target, variant, "beta", round(fit["beta"], 4), "se", round(fit["se_beta"], 4), "orig", round(o["fit"]["beta"], 4),
                  x["diff_capture@5%"], flush=True)
        res["targets"][target] = r
    rt = {t: res["targets"][t]["retrospective"] for t in (2025, 2026)}
    res["pattern"] = cf.pattern({t: v["cross_fit"]["diff_capture@5%"] for t, v in rt.items()}, {t: v["cross_fit"]["fit"] for t, v in rt.items()},
                                {t: abs(v["in_sample_original"]["fit"]["beta"]) for t, v in rt.items()})
    json.dump(res, open(out, "w"), indent=1)
    print("pattern", res["pattern"])


if __name__ == "__main__":
    main()

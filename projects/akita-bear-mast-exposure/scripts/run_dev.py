"""B1: fit M1-M5 on 2023 and score 2024 with the b1 B_env surface, at 500 m and 2 km; choose the radius by M5's
capture@5% (2 km when the difference is below 0.001) and freeze the specification. Reads only the 2023 and
2024 labels. Stops if the frozen specification already exists.

    PYTHONPATH=projects/akita-bear-risk-grid-100m/scripts:projects/akita-bear-mast-exposure/scripts \
      uvx --with numpy --with pandas --with pyarrow --with scikit-learn python run_dev.py BEAR_ART ART MAST_CSV OUTDIR
"""

import json
import os
import sys

import data
import evaluate as ev

TIE = 0.001


def choose(cap500, cap2000):
    return "2000" if abs(cap500 - cap2000) < TIE or cap2000 > cap500 else "500"


def main():
    bear, art, mast_csv, outdir = sys.argv[1:5]
    spec_path = f"{outdir}/b1_frozen_spec.json"
    if os.path.exists(spec_path):
        raise SystemExit(f"{spec_path} exists; the specification is frozen")
    d = data.load(bear, art)
    counts = {t: d["counts"][t] for t in (2023, 2024)}  # nothing later
    s = data.read_mast(mast_csv, "fruiting")
    benv = d["benv"][2024]
    res = {"target": 2024, "train": [2023], "surface": data.SURFACE[2024], "mast": "fruiting", "s": {t: s[t] for t in (2023, 2024)},
           "M0": ev.metrics(benv, counts[2024]), "by_radius": {}}
    for r in ("500", "2000"):
        rr = {}
        for m, cat in ev.MODELS.items():
            e, _ = data.exposure_vec(d["exposure"], f"{cat}_fraction_{r}", d["muni"])
            out = ev.run(benv, e, s, counts, [2023], 2024)
            rr[m] = {"fit": out["fit"], "beta_times_s_target": out["beta_times_s_target"], "metrics": out["metrics"]}
            if m == "M5":
                rr[m]["diff_vs_M0_capture@5%"] = ev.diff(out["score"], benv, counts[2024], d["blocks"])
            print(r, m, round(out["metrics"]["capture@5%"], 4), round(out["fit"]["beta"], 4), flush=True)
        res["by_radius"][r] = rr
    c5, c20 = (res["by_radius"][r]["M5"]["metrics"]["capture@5%"] for r in ("500", "2000"))
    radius = choose(c5, c20)
    res["chosen_radius_m"] = int(radius)
    json.dump(res, open(f"{outdir}/b1_dev_scores.json", "w"), indent=1)
    spec = {
        "frozen": "2026-10-29, after B1 and before any 2025 or 2026 score of M1-M5",
        "radius_m": int(radius), "features": {m: f"{c}_fraction_{radius}" for m, c in ev.MODELS.items()},
        "primary": "M5 retrospective, capture@5% difference from M0 per target year",
        "mast": {"retrospective": "5 - fruiting index of the same year", "operational": "5 - flowering index of the same year",
                 "values": {"fruiting": {t: s[t] for t in (2023, 2024, 2025, 2026)},
                            "flowering": {t: v for t, v in data.read_mast(mast_csv, "flowering").items() if 2023 <= t <= 2026}}},
        "model": "logit P = alpha_t + logit(B_env) [offset] + beta * mast_scarcity(t) * E(c); rank by logit(B_env) + beta * s(target) * E",
        "splits": {t: {"train": data.TRAIN[t], "surface": data.SURFACE[t]} for t in (2025, 2026)},
        "exposure_nan": "set to 0 (no mapped vegetation within the radius; water)",
        "bootstrap": {"blocks": "10 km x 10 km (EPSG:6678)", "B": 1000, "seed": 0, "interval": "90%"},
        "rule": "supported if diff > 0 and lo90 > 0 in both 2025 and 2026; one year only: mixed / not confirmed",
        "F1": "all 24 permutations of the 2023-2026 retrospective values; passes if at most 2 of the 23 non-identity reach the true capture@5%",
        "F2": "10 km tiles of the exposure surface permuted (donors >= 90% prefecture cells), 200 times, seed 0, beta refitted; passes if true > 95th percentile",
        "inputs": {"exposure.npz": data.sha256(f"{art}/exposure.npz"), "mast_csv": data.sha256(mast_csv)},
    }
    json.dump(spec, open(spec_path, "w"), indent=1)
    print("radius", radius, "spec sha256", data.sha256(spec_path))


if __name__ == "__main__":
    main()

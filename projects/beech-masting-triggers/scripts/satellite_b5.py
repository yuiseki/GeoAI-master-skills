"""B5: the satellite cues against the fruiting index of the confirmation years 2009-2026, with directions fixed in
the plan (positive) and 95% intervals from resampling years. S1 and S2 are taken at t-1. Auxiliary (exploratory):
S1 against Ts(t-1), the residual of the frozen B1 model against S1, S2, S3, and S3(t) against the loss from
flowering to fruiting.

From repository root:
    uvx --with pandas --with scipy python projects/beech-masting-triggers/scripts/satellite_b5.py \
      projects/beech-masting-triggers/outputs
"""

import argparse
import json
from pathlib import Path

import pandas as pd

import models as md
from stage_b4 import spearman, table, year_boot_spearman

CONFIRM = (2009, 2026)


def lagged(sat, cols, shift):
    s = sat[["pref", "year"] + cols].copy()
    s["year"] = s["year"] + shift
    return s.rename(columns={c: f"{c}_t{'-' if shift > 0 else '+'}{abs(shift)}" if shift else c for c in cols})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    out = a.outputs / "b5_satellite.json"
    if out.exists():
        raise ValueError("already run once")
    d = table(pd.read_csv(a.outputs / "tohoku_beech_index.csv"), pd.read_csv(a.outputs / "cues_weather.csv"))
    sat = pd.read_csv(a.outputs / "cues_satellite.csv")
    d = d.merge(lagged(sat, ["S1", "S2"], 1), on=["pref", "year"], how="left")
    d = d.merge(sat[["pref", "year", "S3"]], on=["pref", "year"], how="left")
    t = d[d.year.between(*CONFIRM)]
    res = {}
    for cue in ("S1_t-1", "S2_t-1"):
        s = t.dropna(subset=[cue, "F"])
        lo, hi = year_boot_spearman(s, cue, "F", q=(.025, .975))
        res[cue] = {"rows": len(s), "years": int(s.year.nunique()), "spearman": spearman(s[cue], s.F),
                    "ci95": [lo, hi], "supported": bool(lo > 0)}
    b1 = json.loads((a.outputs / "b1_frozen_models.json").read_text(encoding="utf-8"))
    m = b1["frozen"][b1["chosen"]]
    full = md.complete_rows(t).merge(t[["pref", "year", "S1_t-1", "S2_t-1", "S3"]], on=["pref", "year"], how="left",
                                     suffixes=("", "_y"))
    full["resid"] = full.F - md.predict(m, full)
    aux = {}
    for x, y, frame in (("S1_t-1", "Ts_lag1", t), ("S1_t-1", "resid", full), ("S2_t-1", "resid", full),
                        ("S3", "resid", full), ("S3", "loss", t), ("S3", "F", t), ("S2_t-1", "F_lag", t)):
        s = frame.dropna(subset=[x, y])
        if len(s) > 5:
            aux[f"{x} vs {y}"] = {"rows": len(s), "spearman": spearman(s[x], s[y]),
                                  "ci90": year_boot_spearman(s, x, y)}
    result = {"block": "B5", "claim": "C3", "confirmatory": res, "auxiliary_exploratory": aux}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

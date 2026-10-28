"""B4: does the summer heat of t-1 go with the flowering index of t (the stage where flowers are made)?
Spearman over prefecture-years of the confirmation years 2009-2026, with a 90% interval from resampling years.
Auxiliary (exploratory): the same with the fruiting index, other cues, and the loss from flowering to fruiting.

From repository root:
    uvx --with pandas --with scipy python projects/beech-masting-triggers/scripts/stage_b4.py \
      projects/beech-masting-triggers/outputs
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import models as md

CONFIRM = (2009, 2026)


def spearman(x, y):
    from scipy.stats import spearmanr

    return float(spearmanr(x, y)[0])


def year_boot_spearman(df, x, y, B=2000, seed=0, q=(.05, .95)):
    rng = np.random.default_rng(seed)
    years = np.array(sorted(df.year.unique()))
    groups = {v: df[df.year == v] for v in years}
    vals = []
    for _ in range(B):
        s = pd.concat([groups[v] for v in rng.choice(years, len(years))])
        vals.append(spearman(s[x], s[y]))
    return [float(np.nanquantile(vals, q[0])), float(np.nanquantile(vals, q[1]))]


def table(index, cues):
    fl = md.design(index, cues, stage="flowering")[["pref", "year", "F"]].rename(columns={"F": "flower"})
    d = md.design(index, cues).merge(fl, on=["pref", "year"], how="left")
    d["loss"] = d.F - d.flower
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    out = a.outputs / "b4_stage.json"
    if out.exists():
        raise ValueError("already run once")
    d = table(pd.read_csv(a.outputs / "tohoku_beech_index.csv"), pd.read_csv(a.outputs / "cues_weather.csv"))
    t = d[d.year.between(*CONFIRM)].dropna(subset=["flower", "Ts_lag1"])
    main_rho = spearman(t.Ts_lag1, t.flower)
    ci = year_boot_spearman(t, "Ts_lag1", "flower")
    aux = {}
    for x, y in (("Ts_lag1", "F"), ("dT", "flower"), ("dT", "F"), ("Ts_lag2", "flower"), ("F_lag", "flower"),
                 ("F_lag", "F"), ("Tsp", "loss"), ("Tsp", "F"), ("flower", "F")):
        s = t.dropna(subset=[x, y])
        aux[f"{x} vs {y}"] = {"rows": len(s), "spearman": spearman(s[x], s[y]), "ci90": year_boot_spearman(s, x, y)}
    dev = d[d.year.between(1990, 2008)].dropna(subset=["flower", "Ts_lag1"])
    result = {"block": "B4", "claim": "C2", "rows": len(t), "years": int(t.year.nunique()),
              "Ts_lag1_vs_flowering": {"spearman": main_rho, "ci90": ci}, "supported": bool(ci[0] > 0),
              "auxiliary_exploratory": aux,
              "dev_period_descriptive": {"rows": len(dev), "Ts_lag1_vs_flowering": spearman(dev.Ts_lag1, dev.flower)}}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

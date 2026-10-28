"""B1: choose among the candidate models on the development years only (target years 1990-2008), by
leave-one-year-out RMSE of the fruiting index, and freeze the chosen model, M0, M1 and the placebo of the chosen
model, each fitted on all development rows. Rows of later years are dropped before anything is computed.

From repository root:
    uvx --with pandas python projects/beech-masting-triggers/scripts/select_b1.py projects/beech-masting-triggers/outputs
"""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import models as md

DEV = (1990, 2008)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    out = a.outputs / "b1_frozen_models.json"
    if out.exists():
        raise ValueError("already frozen; refusing to refit after the fact")
    index = pd.read_csv(a.outputs / "tohoku_beech_index.csv")
    cues = pd.read_csv(a.outputs / "cues_weather.csv")
    d = md.design(index, cues)
    d = d[d.year.between(*DEV)].reset_index(drop=True)  # nothing after 2008 from here on
    full = md.complete_rows(d)
    dropped = d[~d.set_index(["pref", "year"]).index.isin(full.set_index(["pref", "year"]).index)]
    scores = {m: md.rmse(full.F, md.loyo(full, f)) for m, f in md.CANDIDATES.items()}
    chosen = md.choose(scores)
    frozen = {name: md.fit(full, md.CANDIDATES[name]) for name in ("M0", "M1", chosen)}
    frozen["placebo"] = md.fit(full, md.placebo(md.CANDIDATES[chosen]))
    for name, m in frozen.items():
        m["in_sample_rmse"] = md.rmse(full.F, md.predict(m, full))
    result = {"block": "B1", "mode": "exploratory (development years only)", "dev_target_years": list(DEV),
              "rows": len(full), "years": int(full.year.nunique()),
              "dropped_rows": [f"{r.year} {r.pref}" for r in dropped.itertuples()],
              "loyo_rmse": scores, "chosen": chosen, "chosen_features": md.CANDIDATES[chosen], "frozen": frozen}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    print(text)
    print("sha256", hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    main()

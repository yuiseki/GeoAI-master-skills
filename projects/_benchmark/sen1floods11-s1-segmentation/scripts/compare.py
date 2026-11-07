"""Paired per-chip differences of the all-water IoU, seed by seed: outputs/compare.csv.
Intervals resample chips, and whole flood events (test only; Bolivia is one event).

  python3 scripts/compare.py
"""

import csv
from pathlib import Path

import numpy as np

from run import OUT, boot

PAIRS = [("fcn", "otsu", "B1"), ("unet", "fcn", "B2"), ("unet", "otsu", "B2")]


def chips(tag, split):
    r = [x for x in csv.DictReader(open(OUT / f"chips_{tag}.csv", encoding="utf-8")) if x["split"] == split]
    return {x["chip"]: (float(x["aw"]), x["event"]) for x in r}


rows = []
for a, b, block in PAIRS:
    for split in ("test", "bolivia"):
        for seed in (1, 2, 3):
            ta = f"{a}_s{seed}" if a != "otsu" else "otsu"
            tb = f"{b}_s{seed}" if b != "otsu" else "otsu"
            ca, cb = chips(ta, split), chips(tb, split)
            keys = sorted(ca)
            d = np.array([ca[k][0] - cb[k][0] for k in keys])
            ev = [ca[k][1] for k in keys]
            lo, hi = boot(d, np.arange(len(d)))
            elo, ehi = boot(d, ev) if len(set(ev)) > 1 else ("", "")
            rows.append(dict(block=block, split=split, a=ta, b=tb, chips=len(d), diff=round(float(d.mean()), 4),
                             ci_chip_low=round(float(lo), 4), ci_chip_high=round(float(hi), 4),
                             ci_event_low=round(float(elo), 4) if elo != "" else "",
                             ci_event_high=round(float(ehi), 4) if ehi != "" else "",
                             chips_a_better=int((d > 0).sum()), chips_b_better=int((d < 0).sum())))
            print(rows[-1])
with open(OUT / "compare.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

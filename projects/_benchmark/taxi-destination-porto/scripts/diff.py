"""Paired differences of the mean error between two models on the same prefixes, with a 95% interval that resamples whole
cut times (both models together): outputs/diff.csv. Run after `run.py eval` for both variants.

  python3 scripts/diff.py
"""

import csv
from pathlib import Path

import numpy as np

from run import ART, OUT, boot_by_cut

PAIRS = [  # (variant, test, worse, better, block)
    ("rand", "test", "M1_last_point", "M2_rand_mlp_s1", "B1"),
    ("rand", "test", "M0_centre", "M2_rand_mlp_s1", "B1"),
    ("rand", "test", "M3_rand_noemb_s1", "M2_rand_mlp_s1", "B3"),
    ("rand", "kaggle", "M1_last_point", "M2_rand_mlp_s1", "B1"),
    ("late", "test", "M1_last_point", "M2_late_mlp_s1", "B2"),
    ("late", "late", "M1_last_point", "M2_late_mlp_s1", "B2"),
]
rows = []
for variant, test, worse, better, block in PAIRS:
    a, b = ART / f"err_{variant}_{test}_{worse}.npy", ART / f"err_{variant}_{test}_{better}.npy"
    if not (a.exists() and b.exists()):
        print("missing", a.name, b.name)
        continue
    d = np.load(a) - np.load(b)
    s = np.load(ART / f"split_{variant}.npz")
    group = s[test + "_cut"] if test != "kaggle" else np.arange(len(d))
    lo, hi = boot_by_cut(d, group)
    rows.append(dict(block=block, variant=variant, test=test, worse=worse, better=better, n=len(d),
                     diff_km=round(float(d.mean()), 4), ci_low=round(float(lo), 4), ci_high=round(float(hi), 4)))
    print(rows[-1])
with open(OUT / "diff.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

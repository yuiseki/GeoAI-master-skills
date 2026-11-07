"""Exploratory (after the main results): per-chip Otsu on the VH band with the skill's otsu_mask, against the authors'
S1OtsuLabelHand and against the hand labels: outputs/otsu_own.csv.

  python3 scripts/otsu_own.py
"""

import csv

import numpy as np

from run import OUT, RAW, load, read
from s1f11 import chip_iou, pooled_iou
from seg_eval_skill_copy import otsu_mask

rows = []
for split in ("test", "bolivia"):
    data = load(split)
    own, auth, agree = [], [], []
    for d in data:
        vh = read(RAW / "S1Hand" / f"{d['chip']}_S1Hand.tif")[1]
        o = otsu_mask(vh)
        a = (read(RAW / "S1OtsuLabelHand" / f"{d['chip']}_S1OtsuLabelHand.tif")[0] == 1).astype("int64")
        own.append(o)
        auth.append(a)
        agree.append(float((o == a).mean()))
    rows.append(dict(split=split, chips=len(data),
                     own_aw_chip_mean=round(float(np.mean([chip_iou(o, d["y"]) for o, d in zip(own, data)])), 4),
                     authors_aw_chip_mean=round(float(np.mean([chip_iou(a, d["y"]) for a, d in zip(auth, data)])), 4),
                     own_aw_pooled=round(pooled_iou(own, [d["y"] for d in data]), 4),
                     pixel_agreement_median=round(float(np.median(agree)), 4),
                     pixel_agreement_min=round(float(np.min(agree)), 4)))
    print(rows[-1])
with open(OUT / "otsu_own.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

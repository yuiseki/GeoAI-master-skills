"""Exploratory (after the main results): the authors' Otsu labels came from one VH threshold per flood event
(Sen1Floods11_Metadata.geojson VH_thresh) applied to a focal-mean smoothed VH. Rebuild them with the given thresholds
and focal windows of 1, 3, 5 pixels, and compare with S1OtsuLabelHand and the hand labels: outputs/otsu_event.csv.

  python3 scripts/otsu_event.py
"""

import csv
import json

import numpy as np
from scipy.ndimage import uniform_filter

from run import OUT, RAW, load, read
from s1f11 import chip_iou

meta = json.load(open(RAW / "Sen1Floods11_Metadata.geojson", encoding="utf-8"))
thresh = {f["properties"]["location"]: float(f["properties"]["VH_thresh"]) for f in meta["features"]}
thresh["Mekong"] = thresh["Cambodia"]          # the Mekong chips are the Cambodia event
rows = []
for split in ("test", "bolivia"):
    data = load(split)
    for win in (1, 3, 5):
        ious, agree = [], []
        for d in data:
            vh = read(RAW / "S1Hand" / f"{d['chip']}_S1Hand.tif")[1].astype("float64")
            ok = np.isfinite(vh)
            sm = uniform_filter(np.where(ok, vh, 0.0), win) / np.maximum(uniform_filter(ok.astype(float), win), 1e-9)
            m = (ok & (sm < thresh[d["event"]])).astype("int64")
            a = (read(RAW / "S1OtsuLabelHand" / f"{d['chip']}_S1OtsuLabelHand.tif")[0] == 1).astype("int64")
            ious.append(chip_iou(m, d["y"]))
            agree.append(float((m == a).mean()))
        rows.append(dict(split=split, focal_window=win, aw_chip_mean=round(float(np.mean(ious)), 4),
                         pixel_agreement_with_authors_median=round(float(np.median(agree)), 4),
                         pixel_agreement_min=round(float(np.min(agree)), 4)))
        print(rows[-1], flush=True)
with open(OUT / "otsu_event.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

"""Exploratory (after the main results): one threshold per flood event from the skill's scene_otsu_threshold over all
chips of the event (VH, 100-pixel = 1 km cells, the top share by standard deviation), compared with the authors'
VH_thresh, and scored on the test chips after a 5-pixel focal mean: outputs/otsu_scene.csv, outputs/otsu_scene_events.csv.

  python3 scripts/otsu_scene.py
"""

import csv
import json

import numpy as np

from run import OUT, RAW, chips, load, read
from s1f11 import chip_iou
from seg_eval_skill_copy import focal_mean, scene_otsu_threshold

meta = json.load(open(RAW / "Sen1Floods11_Metadata.geojson", encoding="utf-8"))
given = {f["properties"]["location"]: float(f["properties"]["VH_thresh"]) for f in meta["features"]}
given["Mekong"] = given["Cambodia"]
by_event = {}
for s in ("train", "valid", "test", "bolivia"):
    for c in chips(s):
        by_event.setdefault(c.split("_")[0], []).append(c)
vh = {c: read(RAW / "S1Hand" / f"{c}_S1Hand.tif")[1].astype("float64") for cs in by_event.values() for c in cs}
ev_rows, rows = [], []
for top in (0.1, 0.25):
    th = {}
    for e, cs in sorted(by_event.items()):
        th[e] = scene_otsu_threshold(np.concatenate([vh[c] for c in cs], 1), cell=100, top=top)
        ev_rows.append(dict(top=top, event=e, chips=len(cs), own=round(th[e], 2), authors=given[e],
                            diff=round(th[e] - given[e], 2)))
    for split in ("test", "bolivia"):
        data = load(split)
        aw = [chip_iou((focal_mean(vh[d["chip"]], 5) < th[d["event"]]).astype("int64"), d["y"]) for d in data]
        rows.append(dict(top=top, split=split, aw_chip_mean=round(float(np.mean(aw)), 4),
                         median_abs_threshold_diff_db=round(float(np.median([abs(r["diff"]) for r in ev_rows if r["top"] == top])), 2)))
        print(rows[-1], flush=True)
for name, rs in (("otsu_scene_events.csv", ev_rows), ("otsu_scene.csv", rows)):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
for r in ev_rows:
    print(r)

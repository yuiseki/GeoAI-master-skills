"""Exploratory (added after the planned run): why VH added little (claim A3).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with shapely python scripts/06_explore_a3.py

Splits the reference pixels the VV detection missed by two questions: is the pixel inside the zone (step 6), and is
its VH change at or below the threshold (step 8)? Then tries the water level of article 2 (the 99th percentile of the
ground under each part of sure water, instead of the median of its edge) and the article's VH threshold of -3.3 dB,
one at a time and together. Writes outputs/explore_a3.json. Not part of the planned judgement.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
detect_mod = __import__("03_detect")
import sar  # noqa: E402
from sar import floodable, metrics  # noqa: E402


def part_quantile(labels, dem, q):
    return {k: float(np.nanquantile(dem[labels == k], q)) for k in range(1, labels.max() + 1)}


def main():
    g = detect_mod.load_grid()
    win = np.load(detect_mod.ART / "windows.npz")["buffer"]
    r = detect_mod.run(g)
    ok, water, ref = r["ok"], g["water"], g["ref_0924"]
    valid = win & ~water & ok
    missed = ref & ~r["det_vv"] & valid
    thr = r["fit"]["dvh_land_pct"]
    dark = r["dvh"] <= thr
    split = {"missed_pixels": int(missed.sum()),
             "in_zone_dark": int((missed & r["zone"] & dark).sum()), "in_zone_not_dark": int((missed & r["zone"] & ~dark).sum()),
             "out_zone_dark": int((missed & ~r["zone"] & dark).sum()), "out_zone_not_dark": int((missed & ~r["zone"] & ~dark).sum()),
             "dark_at_-3.3": int((missed & (r["dvh"] <= -3.3)).sum())}
    split["out_zone"] = split["out_zone_dark"] + split["out_zone_not_dark"]
    split["out_zone_share"] = round(split["out_zone"] / split["missed_pixels"], 3)
    split["in_zone_dark_share"] = round(split["in_zone_dark"] / split["missed_pixels"], 3)
    split["out_zone_pct"] = round(100 * split["out_zone_share"], 1)
    split["in_zone_dark_pct"] = round(100 * split["in_zone_dark"] / split["missed_pixels"], 1)
    out = {"vh_threshold_plan_db": round(thr, 3), "split_of_missed": split,
           "missed_dem_median_m": round(float(np.median(g["dem"][missed])), 2),
           "both_dem_median_m": round(float(np.median(g["dem"][ref & r["det_vv"] & valid])), 2), "trials": {}}
    lv99 = part_quantile(r["labels"], g["dem"], 0.99)
    zone99 = floodable(r["labels"], lv99, g["dem"], water & ok)
    for name, zone, t in (("plan", r["zone"], thr), ("level_p99", zone99, thr), ("vh_-3.3", r["zone"], -3.3),
                          ("level_p99_vh_-3.3", zone99, -3.3)):
        with np.errstate(invalid="ignore"):
            dv = zone & ok & ~water & (r["prob"] >= sar.PLAN["post"])
            dvh = dv | (zone & ok & ~water & (r["dvh"] <= t))
        m1, m2 = metrics(ref, dv, valid), metrics(ref, dvh, valid)
        out["trials"][name] = {"zone_km2": round(float(zone.sum()) / 1e4, 3),
                               "vv": {"recall": round(m1["recall"], 3), "precision": round(m1["precision"], 3)},
                               "vvvh": {"recall": round(m2["recall"], 3), "precision": round(m2["precision"], 3),
                                        "missed_km2": round(m2["missed_m2"] / 1e6, 3), "extra_km2": round(m2["extra_m2"] / 1e6, 3)},
                               "vvvh_pct": {"recall": round(100 * m2["recall"], 1), "precision": round(100 * m2["precision"], 1)},
                               "recall_gain": round(m2["recall"] - m1["recall"], 3),
                               "area_vv_km2": round(float(dv.sum()) / 1e4, 3), "area_vvvh_km2": round(float(dvh.sum()) / 1e4, 3)}
    lv = np.array(list(r["levels"].values()))
    l99 = np.array(list(lv99.values()))
    big = int(np.argmax(np.bincount(r["labels"].ravel())[1:])) + 1
    out["levels"] = {"plan_median_of_parts": round(float(np.nanmedian(lv)), 2), "p99_median_of_parts": round(float(np.nanmedian(l99)), 2),
                     "largest_part_plan": round(r["levels"][big], 2), "largest_part_p99": round(lv99[big], 2)}
    (HERE.parent / "outputs/explore_a3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Exploratory (after the results): could the brightening at 田園調布 be found without knowing where to look?
Writes outputs/rank_cells.json and outputs/rank_cells_top.csv.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with scikit-image --with pyproj --with shapely python -u scripts/06_rank_cells.py

The 23 wards' part of the grid (N03 codes 13101 to 13123, not WorldCover water) is cut into 250 m cells (25 x 25 pixels).
A cell is kept if it has at least 200 built-up (WorldCover 50) pixels with a finite dVV. Its score is the share of those
pixels that brightened by 3 dB or more (main settings of 03_blocks.py: orbit 46, 2019-10-13 vs the six pre scenes,
3 x 3, shifted back). The same score on the placebo pair of 05_explore.py (2019-10-06 vs the five earlier scenes).
A cell is a record cell if 20 % or more of its pixels are REC. Also: how much of 大田区 lies inside the grid.
"""
import csv
import json

import numpy as np
import shapely
from pyproj import Transformer

import flood
from common import ART, OUT, RAW, SCENES, UTM

C, MIN_BUILT, REC_SHARE, THR = 25, 200, 0.2, 3.0


def main():
    aux = dict(np.load(ART / "aux.npz"))
    ward, wc, rec = aux["ward"], aux["wc"], aux["rec"]
    shift = json.loads((OUT / "grid_summary.json").read_text(encoding="utf-8"))["orbits"]["46"]["shift_back"]
    st = np.load(ART / "stack_o46.npy", mmap_mode="r")
    roles = [r for r, _ in SCENES[46]]
    pre = [i for i, r in enumerate(roles) if r == "pre"]
    ev = roles.index("event")

    def img(idx):
        a = np.asarray(st[0, idx], float)
        a = np.nanmean(a, axis=0) if a.ndim == 3 else a
        return flood.boxcar(flood.apply_int_shift(a, shift), 3)

    d_ev = flood.ratio_db(img(ev), img(pre))
    d_pl = flood.ratio_db(img(pre[-1]), img(pre[:-1]))
    in23 = (ward >= 13101) & (ward <= 13123) & (wc != 80)
    rows, cols = ward.shape
    cells = []
    for r0 in range(0, rows - C + 1, C):
        for c0 in range(0, cols - C + 1, C):
            s = (slice(r0, r0 + C), slice(c0, c0 + C))
            b = in23[s] & (wc[s] == 50) & np.isfinite(d_ev[s]) & np.isfinite(d_pl[s])
            if b.sum() < MIN_BUILT:
                continue
            w = np.bincount(ward[s][in23[s]]).argmax()
            cells.append({"row": r0, "col": c0, "ward_code": int(w), "built_pixels": int(b.sum()),
                          "rec_share": round(float(rec[s].mean()), 3),
                          "bright_event": round(float((d_ev[s][b] >= THR).mean()), 4),
                          "bright_placebo": round(float((d_pl[s][b] >= THR).mean()), 4)})
    order = sorted(cells, key=lambda x: -x["bright_event"])
    for k, x in enumerate(order):
        x["rank_event"] = k + 1
    for k, x in enumerate(sorted(cells, key=lambda x: -x["bright_placebo"])):
        x["rank_placebo"] = k + 1
    t = aux["transform"]
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    for x in cells:
        lon, lat = to_ll.transform(t[2] + (x["col"] + C / 2) * t[0], t[5] + (x["row"] + C / 2) * t[4])
        x["lon"], x["lat"] = round(lon, 5), round(lat, 5)
    reccells = [x for x in order if x["rec_share"] >= REC_SHARE]
    fc = json.loads((RAW / "vectors/tokyo.geojson").read_text(encoding="utf-8"))
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    ota = [shapely.from_geojson(json.dumps(f["geometry"])) for f in fc["features"] if f["properties"]["N03_007"] == "13111"]
    ota = shapely.union_all([shapely.transform(g, lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
                             for g in ota])
    out = {"note": "exploratory, after the results", "wards": 23, "min_built_pixels": MIN_BUILT, "rec_share_min": REC_SHARE,
           "cells": len(cells), "cell_m": C * 10,
           "record_cells": [{k: x[k] for k in ("ward_code", "rec_share", "bright_event", "rank_event",
                                                "bright_placebo", "rank_placebo", "lon", "lat")} for x in reccells],
           "top10_event": [{k: x[k] for k in ("ward_code", "rec_share", "bright_event", "bright_placebo", "lon", "lat")}
                           for x in order[:10]],
           "median_bright_event": round(float(np.median([x["bright_event"] for x in cells])), 4),
           "ota_pixels_in_grid": int((ward == 13111).sum()), "ota_area_n03_m2_utm": round(ota.area, 0),
           "ota_share_in_grid": round(float((ward == 13111).sum() * 100 / ota.area), 4)}
    (OUT / "rank_cells.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(OUT / "rank_cells_top.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(order[0]))
        w.writeheader()
        w.writerows(order[:50])
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

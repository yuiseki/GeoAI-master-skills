"""Optical dating of the site from Sentinel-2 (D_opt of EXPERIMENT_PLAN.md, block A2).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with shapely --with pyproj python scripts/03_s2.py

For every item in raw/s2/: the pixels whose centre is inside labels/site.geojson, kept where SCL is 4, 5, 6 or 7; the
date is used if at least 80 % of the site pixels are kept. Reflectance = DN / 10000, minus 0.1 from processing baseline
04.00. One value per date (the item with more kept pixels). Each of B02, B03, B04, B08, B11, B12 is divided by its
standard deviation over all used dates, and the dates inside W (2019-04-01 to 2025-03-31) are split into two segments
with the smallest sum of squares (rank.break_2seg, at least 5 dates per segment). D_opt is the first date of the second
segment.

Writes outputs/s2_series.csv (date, item, kept share, the six site means) and outputs/s2_break.json.
"""
import csv
import json

import numpy as np
import shapely
from pyproj import Transformer

from common import HERE, OUT, RAW
from rank import break_2seg

BANDS = ("B02", "B03", "B04", "B08", "B11", "B12")
VALID_SCL = (4, 5, 6, 7)
W = ("2019-04-01", "2025-03-31")


def main():
    fc = json.loads((HERE.parent / "labels/site.geojson").read_text(encoding="utf-8"))
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    t = Transformer.from_crs("EPSG:4326", "EPSG:32654", always_xy=True)
    poly = shapely.Polygon(list(zip(*t.transform([p[0] for p in ring], [p[1] for p in ring]))))
    items = json.loads((RAW / "s2_items.json").read_text(encoding="utf-8"))
    best, n_items, n_cloudy = {}, 0, 0
    mask = None
    for it in items:
        z = np.load(RAW / "s2" / f"{it['id']}.npz")
        n_items += 1
        if mask is None:
            a, b, c, d, e, f = z["transform"]
            rows, cols = z["SCL"].shape
            rr, cc = np.mgrid[0:rows, 0:cols]
            mask = shapely.contains_xy(poly, c + (cc + 0.5) * a, f + (rr + 0.5) * e)
            tr0 = tuple(z["transform"])
        if tuple(z["transform"]) != tr0:
            raise RuntimeError(f"grid differs: {it['id']}")
        keep = np.isin(z["SCL"], VALID_SCL) & mask
        share = keep.sum() / mask.sum()
        if share < 0.8:
            n_cloudy += 1
            continue
        pb = str(z["processing_baseline"])
        off = 0.1 if pb >= "04.00" else 0.0
        vals = [float(z[bnd][keep].astype(float).mean() / 10000 - off) for bnd in BANDS]
        dt = str(z["datetime"])[:10]
        if dt not in best or share > best[dt]["share"]:
            best[dt] = {"date": dt, "item": it["id"], "share": round(float(share), 4), "baseline": pb,
                        **{bnd: round(v, 5) for bnd, v in zip(BANDS, vals)}}
    rows_out = [best[d] for d in sorted(best)]
    with open(OUT / "s2_series.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    Y = np.array([[r[b] for b in BANDS] for r in rows_out])
    Y = Y / Y.std(0)
    inw = np.array([W[0] <= r["date"] <= W[1] for r in rows_out])
    dw = [r["date"] for r in rows_out if W[0] <= r["date"] <= W[1]]
    k, sse = break_2seg(Y[inw], min_seg=5)
    before, after = Y[inw][:k].mean(0), Y[inw][k:].mean(0)
    raw = np.array([[r[b] for b in BANDS] for r in rows_out])[inw]
    out = {"items": n_items, "items_below_80pct_clear": n_cloudy, "dates_used": len(rows_out), "dates_in_W": len(dw),
           "site_pixels": int(mask.sum()), "D_opt": dw[k], "last_date_before": dw[k - 1],
           "mean_reflectance_before": dict(zip(BANDS, [round(float(v), 4) for v in raw[:k].mean(0)])),
           "mean_reflectance_after": dict(zip(BANDS, [round(float(v), 4) for v in raw[k:].mean(0)])),
           "sse_min": round(float(np.nanmin(sse)), 3), "sse_by_date": {d: (None if np.isnan(s) else round(float(s), 3))
                                                                        for d, s in zip(dw, sse)}}
    (OUT / "s2_break.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print({k_: v for k_, v in out.items() if k_ != "sse_by_date"})


if __name__ == "__main__":
    main()

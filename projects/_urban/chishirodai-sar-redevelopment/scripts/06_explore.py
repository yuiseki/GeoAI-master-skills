"""Exploratory checks made after the confirmatory results (not in EXPERIMENT_PLAN.md). Writes outputs/explore.json.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with pyproj python scripts/06_explore.py

1. background: per WorldCover class, the share of pixels whose FY mean differs by 3 dB or more, for FY2024 vs FY2019
   (the main score) and FY2018 vs FY2019 (one year apart), VV and VH, with the median and standard deviation of the dB
   difference
2. coregistration: the mean shift (rows, cols) of each fiscal year from grid_summary.json, and the built-up share of
   the FY2024 vs FY2019 VV difference >= 3 dB when every date is first shifted back by its measured shift (linear
   interpolation; both years interpolated) compared with no shift (also interpolated, to keep the smoothing equal)
3. site: the mean VV and VH dB of SITE in FY2019 and FY2024 (mean of the per-date site means in site_series.csv), and
   the share of SITE pixels whose FY2024 vs FY2019 VV mean fell by 3 dB or more
4. site series: the mean of the per-date SITE VV dB over 2023-01-01..2023-10-31 and over 2023-12-01..2024-11-30
5. capture: from the capture curves in blocks.json, the fewest tiles that hold half and 80 % of the label-2 tiles
"""
import csv
import json

import numpy as np
from scipy import ndimage

from common import ART, OUT

CLASSES = {10: "tree", 30: "grass", 40: "crop", 50: "built"}


def main():
    aux = np.load(ART / "aux.npz")
    st = np.load(ART / "stack.npy", mmap_mode="r")
    dates = [str(d) for d in aux["dates"]]
    wc, site = aux["wc"], aux["site"]
    shifts = json.loads((OUT / "grid_summary.json").read_text(encoding="utf-8"))["shifts"]
    fys = {"FY2018": ("2018-04-01", "2019-03-31"), "FY2019": ("2019-04-01", "2020-03-31"),
           "FY2024": ("2024-04-01", "2025-03-31")}

    def sel(fy):
        return [i for i, d in enumerate(dates) if fys[fy][0] <= d <= fys[fy][1]]

    def fy_mean(fy, k):
        return np.nanmean(np.asarray(st[k, sel(fy)], float), axis=0)

    out = {"background": {}}
    for pair in (("FY2024", "FY2019"), ("FY2018", "FY2019")):
        for k, pol in ((0, "vv"), (1, "vh")):
            d = 10 * np.log10(fy_mean(pair[0], k) / fy_mean(pair[1], k))
            for c, name in CLASSES.items():
                m = (wc == c) & np.isfinite(d)
                out["background"][f"{pair[0]}_vs_{pair[1]}_{pol}_{name}"] = {
                    "pixels": int(m.sum()), "median_db": round(float(np.median(d[m])), 3),
                    "sd_db": round(float(d[m].std()), 3), "share_abs_ge_3db": round(float((np.abs(d[m]) >= 3).mean()), 4)}
            if pair[0] == "FY2024" and k == 0:
                out["site"] = {"share_vv_fell_3db": round(float((d[site] <= -3).mean()), 4),
                               "median_vv_db_change": round(float(np.median(d[site])), 3)}

    out["coregistration"] = {fy: [round(float(v), 3) for v in np.mean([shifts[dates[i]] for i in sel(fy)], axis=0)]
                             for fy in fys}

    def fy_mean_shifted(fy, reg):
        acc = []
        for i in sel(fy):
            x = np.asarray(st[0, i], float)
            x = np.nan_to_num(x, nan=np.nanmean(x))
            acc.append(ndimage.shift(x, shifts[dates[i]] if reg else [0.0, 0.0], order=1, mode="nearest"))
        return np.mean(acc, axis=0)
    for reg in (False, True):
        d = np.abs(10 * np.log10(fy_mean_shifted("FY2024", reg) / fy_mean_shifted("FY2019", reg)))
        out["coregistration"]["built_share_ge_3db_" + ("shifted_back" if reg else "not_shifted")] = \
            round(float((d[wc == 50] >= 3).mean()), 4)

    with open(OUT / "site_series.csv", encoding="utf-8") as f:
        ss = list(csv.DictReader(f))
    for fy in ("FY2019", "FY2024"):
        rows = [r for r in ss if fys[fy][0] <= r["date"] <= fys[fy][1]]
        out["site"][f"{fy}_site_vv_db"] = round(float(np.mean([float(r["site_vv_db"]) for r in rows])), 2)
        out["site"][f"{fy}_site_vh_db"] = round(float(np.mean([float(r["site_vh_db"]) for r in rows])), 2)
    for name, a, b in (("2023-01_to_2023-10", "2023-01-01", "2023-10-31"), ("2023-12_to_2024-11", "2023-12-01", "2024-11-30")):
        rows = [r for r in ss if a <= r["date"] <= b]
        out["site"][f"vv_db_{name}"] = round(float(np.mean([float(r["site_vv_db"]) for r in rows])), 2)
        out["site"][f"dates_{name}"] = len(rows)
    cc = json.loads((OUT / "blocks.json").read_text(encoding="utf-8"))["B_capture_curve"]
    out["capture"] = {}
    for name in ("sar", "builtup"):
        for share in (0.5, 0.8):
            k = next(i for i, h in enumerate(cc[name]) if h >= share * cc["positives_2"])
            out["capture"][f"{name}_tiles_for_{int(share * 100)}pct"] = k
            out["capture"][f"{name}_tile_share_for_{int(share * 100)}pct"] = round(k / (len(cc[name]) - 1), 3)
    (OUT / "explore.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

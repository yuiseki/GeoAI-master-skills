"""Exploratory (added after the planned run of stage B): what sets the 09-24 surface of the polder part.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with pyproj python scripts/14_explore_b.py

For the satellite part P of 09-24 (our GRD water, the part holding most of the 10-01 outline): the quantiles of the
ground under it; how many of its pixels are above the GSI surface interpolated to 17:41, and where they are (inside
the GSI 09-24 outline or not, filled from DEM10B or not, next to permanent water or not); and the share of the GSI
09-24 outline inside P that the satellite water covers by GSI depth band. Writes outputs/explore_b.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
dp = __import__("11_depth")
fb = dp.fb
from sarb import parts  # noqa: E402


def main():
    g = dict(np.load(fb.ART / "grid.npz"))
    w = dict(np.load(fb.ART / "water_b.npz"))
    blocks = json.loads((HERE.parent / "outputs/blocks_b.json").read_text(encoding="utf-8"))
    s_ref = blocks["main"]["E2"]["gsi_interp_0924_1741_m"]
    mask = w["w0924"] & ~g["water"]
    lab = parts(mask, 100)
    P = lab == dp.overlap_part(lab, g["ref_1001"])
    dem = g["dem"]
    q = [0.5, 0.9, 0.95, 0.98, 0.99, 0.995]
    high = P & (dem > s_ref)
    near_water = ndimage.binary_dilation(g["water"], iterations=3)
    out = {"P_pixels": int(P.sum()), "ground_quantiles_m": {str(k): round(float(v), 3) for k, v in zip(q, np.quantile(dem[P], q))},
           "gsi_surface_interp_m": s_ref,
           "above_gsi_surface": {"pixels": int(high.sum()), "share": round(float(high.sum() / P.sum()), 4),
                                 "inside_gsi_0924_outline": int((high & g["ref_0924"]).sum()),
                                 "dem10b_filled": int((high & (g["dem_src"] == 2)).sum()),
                                 "within_30m_of_permanent_water": int((high & near_water).sum()),
                                 "above_5m": int((P & (dem > 5)).sum())},
           "P_share_inside_gsi_0924_outline": round(float((P & g["ref_0924"]).sum() / P.sum()), 4)}
    # the same analysis with the ground only where DEM5A has a value (the DEM10B fill over water left out)
    g5 = {**g, "dem": np.where(g["dem_src"] == 1, dem, np.nan)}
    gsi = dict(np.load(fb.ART / "gsi_depth.npz"))
    r5 = dp.analyse(g5, w, gsi)[0]
    out["dem5a_only"] = {"E1": r5["E1"], "E2": r5["E2"], "E3": r5["E3"], "E4": r5["E4"], "E5": r5["E5"], "E6": r5["E6"], "E7": r5["E7"],
                         "polder": r5["polder"], "judgement": {k: v["reproduced"] for k, v in dp.judge(r5).items()}}
    (HERE.parent / "outputs/explore_b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

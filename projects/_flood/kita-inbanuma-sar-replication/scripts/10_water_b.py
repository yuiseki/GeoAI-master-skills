"""Satellite water of 2026-09-24 (before 09-12), 10-01 (orbit 141, before 09-19) and 10-06 (before 09-12) from our
GRD processing, with the detection of stage A and its planned settings (the plan as changed on 2026-10-31). The
water from the RTC scenes (09-24 of stage A, 10-01 of orbit 141) is kept for the robustness rows.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with pyproj python scripts/10_water_b.py

Writes artifacts/.../water_b.npz (w0924, w1001, w1006, their VV-only ones, and the RTC ones) and outputs/water_b.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.warp import Resampling, reproject

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fb = __import__("07_fetch_b")
from sar import detect, to_db  # noqa: E402

OUT = HERE.parent / "outputs"


def rtc_on_grid(name, g):
    """An orbit 141 RTC cut, put on the analysis grid (bilinear in linear power), in dB."""
    shape = g["vv_a"].shape
    out = np.full(shape, np.nan, np.float32)
    with rasterio.open(fb.RAW_B / f"rtc141_{name}.tif") as src:
        a = src.read(1).astype(np.float32)
        a[a == src.nodata] = np.nan
        reproject(a, out, src_transform=src.transform, src_crs=src.crs, dst_transform=Affine(*g["transform"]),
                  dst_crs=src.crs, resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
        aligned = all(abs(v / 10 - round(v / 10)) < 1e-6 for v in (src.transform.c - g["transform"][2], src.transform.f - g["transform"][5]))
    return to_db(out), aligned


def run(g, vv_b, vh_b, vv_a, vh_a):
    return detect(vv_b, vh_b, vv_a, vh_a, g["dem"], g["water"])


def main():
    g = dict(np.load(fb.ART / "grid.npz"))
    a = np.load(fb.ART / "detect_plan.npz")
    out = {"w0924_rtc": a["det_vvvh"], "w0924_rtc_vv": a["det_vv"]}
    info = {}
    for after, before in (("0924", "0912"), ("1001", "0919"), ("1006", "0912")):
        g0, g1 = np.load(fb.ART / f"grd_{before}.npz"), np.load(fb.ART / f"grd_{after}.npz")
        r = run(g, g0["vv"], g0["vh"], g1["vv"], g1["vh"])
        out[f"w{after}"], out[f"w{after}_vv"] = r["det_vvvh"], r["det_vv"]
        info[after] = {"before": before, "fit": r["fit"], "missing": int((~r["ok"]).sum())}
    b = {}
    for name in ("0919_vv", "0919_vh", "1001_vv", "1001_vh"):
        b[name], aligned = rtc_on_grid(name, g)
        info.setdefault("rtc141_grid_aligned", {})[name] = bool(aligned)
    r = run(g, b["0919_vv"], b["0919_vh"], b["1001_vv"], b["1001_vh"])
    out["w1001_rtc"], out["w1001_rtc_vv"] = r["det_vvvh"], r["det_vv"]
    for k, v in out.items():
        info.setdefault("area_km2", {})[k] = round(float(v.sum()) * 100 / 1e6, 4)
    np.savez_compressed(fb.ART / "water_b.npz", **out)
    (OUT / "water_b.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()

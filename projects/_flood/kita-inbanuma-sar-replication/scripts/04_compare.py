"""Blocks B1 to B5 of EXPERIMENT_PLAN.md, the planned judgement of claims A1 to A5, and the robustness variants.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with scipy --with shapely --with pyproj python scripts/04_compare.py

Writes outputs/blocks.json and artifacts/.../windows.npz (the comparison windows).
"""
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import shapely
from affine import Affine
from pyproj import Transformer
from rasterio.features import rasterize

from sar import buffer_for_area, metrics

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
detect_mod = __import__("03_detect")
ART = detect_mod.ART
UTM = "EPSG:32654"
TARGET_M2 = 38e6
VARIANTS = {"post_0.3": {"post": 0.3}, "post_0.7": {"post": 0.7}, "min_size_25": {"min_size": 25},
            "min_size_400": {"min_size": 400}, "level_q_0.75": {"level_q": 0.75}, "vh_pct_5": {"vh_pct": 5.0},
            "no_zone": {"use_floodable": False}}


def outline_utm(day):
    con = duckdb.connect()
    con.execute("load spatial")
    wkb = con.sql(f"select st_aswkb(geometry) from '{ART / 'raw/inundation_kita_inbanuma.parquet'}' "
                  f"where strftime(version_time, '%Y-%m-%d') = '{day}'").fetchall()
    assert len(wkb) == 1
    t = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    return shapely.transform(shapely.from_wkb(bytes(wkb[0][0])), lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))


def km2(m2):
    return round(m2 / 1e6, 3)


def pct_stats(r, valid, ref):
    """Medians (dB) per class of the VV detection against the reference."""
    cls = {"both": ref & r["det_vv"], "missed": ref & ~r["det_vv"], "extra": ~ref & r["det_vv"],
           "neither": ~ref & ~r["det_vv"]}
    out = {}
    for name, m in cls.items():
        m = m & valid
        out[name] = {"pixels": int(m.sum())}
        for k, a in (("dvv", r["dvv"]), ("dvh", r["dvh"]), ("vv_b", r["vv_b"]), ("vv_a", r["vv_a"]),
                     ("vh_b", r["vh_b"]), ("vh_a", r["vh_a"])):
            out[name][k] = round(float(np.median(a[m])), 2) if m.any() else None
    return out


def blocks(g, r, valid, core):
    ref = g["ref_0924"]
    r = {**r, "vv_b": g["vv_b"], "vv_a": g["vv_a"], "vh_b": g["vh_b"], "vh_a": g["vh_a"]}
    m_vv, m_vvvh = metrics(ref, r["det_vv"], valid), metrics(ref, r["det_vvvh"], valid)
    b = {"B1": {"core_pixels": int(core.sum()), "share_det_vv": round(float(r["det_vv"][core].mean()), 3)},
         "B2": {k: (km2(v) if k.endswith("m2") else round(v, 3)) for k, v in m_vv.items()},
         "B3": {k: (km2(v) if k.endswith("m2") else round(v, 3)) for k, v in m_vvvh.items()},
         "B4": pct_stats(r, valid, ref),
         "B5": {"det_vv_km2": km2(r["det_vv"].sum() * 100), "det_vvvh_km2": km2(r["det_vvvh"].sum() * 100)}}
    for k in ("B2", "B3"):
        b[k]["recall_pct"], b[k]["precision_pct"] = round(100 * b[k]["recall"], 1), round(100 * b[k]["precision"], 1)
    b["B1"]["share_pct"] = round(100 * b["B1"]["share_det_vv"], 1)
    b["B1"]["rule_min_pct"] = 90
    b["B3"]["recall_gain"] = round(m_vvvh["recall"] - m_vv["recall"], 3)
    b["B3"]["precision_change"] = round(m_vvvh["precision"] - m_vv["precision"], 3)
    b["B3"]["missed_ratio"] = round(m_vvvh["missed_m2"] / m_vv["missed_m2"], 3) if m_vv["missed_m2"] else None
    b["B5"]["ratio"] = round(b["B5"]["det_vvvh_km2"] / b["B5"]["det_vv_km2"], 3) if b["B5"]["det_vv_km2"] else None
    return b


def judge(b):
    """The rules of 主張の地図. Each claim: the conditions and whether all hold."""
    b4 = b["B4"]
    c = {"A1": {"core_share_ge_0.90": b["B1"]["share_det_vv"] >= 0.90},
         "A2": {"recall_41_71": 0.41 <= b["B2"]["recall"] <= 0.71, "precision_ge_0.74": b["B2"]["precision"] >= 0.74,
                "recall_lt_precision": b["B2"]["recall"] < b["B2"]["precision"]},
         "A3": {"recall_gain_ge_0.10": b["B3"]["recall_gain"] >= 0.10, "precision_down": b["B3"]["precision_change"] < 0,
                "missed_ratio_le_0.7": b["B3"]["missed_ratio"] is not None and b["B3"]["missed_ratio"] <= 0.7},
         "A4": {"missed_dvh_1db_below_dvv": b4["missed"]["dvh"] is not None and b4["missed"]["dvh"] <= b4["missed"]["dvv"] - 1,
                "both_dvv_le_-8": b4["both"]["dvv"] is not None and b4["both"]["dvv"] <= -8},
         "A5": {"vv_2.4_7.2": 2.4 <= b["B5"]["det_vv_km2"] <= 7.2, "ratio_ge_1.5": (b["B5"]["ratio"] or 0) >= 1.5}}
    return {k: {"conditions": {n: bool(x) for n, x in v.items()}, "reproduced": bool(all(v.values()))} for k, v in c.items()}


def main():
    g = detect_mod.load_grid()
    transform = Affine(*g["transform"])
    shape = g["vv_a"].shape
    o24 = outline_utm("2026-09-24")
    d = buffer_for_area(o24, TARGET_M2)
    win = rasterize([o24.buffer(d)], out_shape=shape, transform=transform).astype(bool)
    win_bbox = rasterize([shapely.box(*o24.bounds)], out_shape=shape, transform=transform).astype(bool)
    np.savez_compressed(ART / "windows.npz", buffer=win, bbox=win_bbox)

    r = detect_mod.run(g)
    valid = win & ~g["water"] & r["ok"]
    core = g["ref_1001"] & ~g["water"] & r["ok"]
    main_b = blocks(g, r, valid, core)
    out = {"window": {"buffer_m": round(d, 1), "buffer_km2": km2(o24.buffer(d).area), "window_pixels": int(win.sum()),
                      "window_km2_without_water": km2(valid.sum() * 100), "water_pixels_in_window": int((win & g["water"]).sum()),
                      "bbox_km2": km2(shapely.box(*o24.bounds).area)},
           "main": main_b, "judgement": judge(main_b), "variants": {}}
    for name, kw in VARIANTS.items():
        rv = detect_mod.run(g, **kw)
        bv = blocks(g, rv, valid, core)
        out["variants"][name] = {"B1": bv["B1"]["share_det_vv"], "B1_pct": bv["B1"]["share_pct"], "B2": bv["B2"], "B3": bv["B3"], "B5": bv["B5"],
                                 "judgement": {k: v["reproduced"] for k, v in judge(bv).items()}}
    vb = win_bbox & ~g["water"] & r["ok"]
    bb = blocks(g, r, vb, core)
    out["variants"]["window_bbox"] = {"B2": bb["B2"], "B3": bb["B3"],
                                      "judgement": {k: v["reproduced"] for k, v in judge(bb).items()}}
    (HERE.parent / "outputs/blocks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"window": out["window"], "main": {k: v for k, v in main_b.items() if k != "B4"},
                      "judgement": {k: v["reproduced"] for k, v in out["judgement"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

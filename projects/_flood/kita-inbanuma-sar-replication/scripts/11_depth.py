"""Water surfaces and depths of article 2, blocks E1 to E7 of EXPERIMENT_PLAN_B.md with the planned judgement of
claims D1 to D7, and the robustness variants.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with pyproj python scripts/11_depth.py

Writes outputs/blocks_b.json and artifacts/.../depth_b.npz (the satellite depths and the maximum depth).
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fb = __import__("07_fetch_b")
from sarb import depth_from_surfaces, extrapolate, parts, surface_iou, surface_quantile  # noqa: E402

OUT = HERE.parent / "outputs"
JST = timezone(timedelta(hours=9))
T = {"0922": datetime(2026, 9, 22, 14, 0, tzinfo=JST), "0924": datetime(2026, 9, 24, 14, 0, tzinfo=JST),
     "0925": datetime(2026, 9, 25, 11, 0, tzinfo=JST), "1001": datetime(2026, 10, 1, 16, 0, tzinfo=JST),
     "s0924": datetime(2026, 9, 24, 17, 41, tzinfo=JST), "s1001": datetime(2026, 10, 1, 17, 32, tzinfo=JST),
     "s1006": datetime(2026, 10, 6, 17, 41, tzinfo=JST)}
BANDS = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, np.inf)]
ARTICLE = {"0922": 2.88, "0924": 2.19, "0925": 1.38, "1001": 0.83}


def hours(t):
    return (T[t] - T["0922"]).total_seconds() / 3600


def surfaces(labels, water, dem, rule, q=0.99):
    out = {}
    for k in range(1, labels.max() + 1):
        part = labels == k
        out[k] = surface_quantile(part, dem, q) if rule == "quantile" else surface_iou(part, water, dem)[0]
    return out


def km2(n):
    return round(float(n) * 100 / 1e6, 4)


def overlap_part(labels, region):
    """The label overlapping region most (0 if none)."""
    v = labels[region & (labels > 0)]
    return int(np.bincount(v).argmax()) if len(v) else 0


def analyse(g, w, gsi, rule0924="quantile", q0924=0.99):
    dem, water_perm = g["dem"], g["water"]
    valid = np.load(fb.ART / "windows.npz")["buffer"] & ~water_perm
    sat = {}
    for tag, rule in (("0924", rule0924), ("1001", "iou"), ("1006", "iou")):
        mask = w[f"w{tag}"] & ~water_perm
        lab = parts(mask, 100)
        s = surfaces(lab, mask, dem, rule, q0924 if tag == "0924" else 0.99)
        sat[tag] = {"labels": lab, "surf": s, "depth": depth_from_surfaces(lab, s, dem), "mask": mask}
    res = {}

    # E1: depth difference and range on 09-24
    gd, sd = gsi["depth_0924"], sat["0924"]["depth"]
    both = valid & ~np.isnan(gd) & ~np.isnan(sd)
    diff = sd[both] - gd[both]
    ref = g["ref_0924"] & valid
    det = sat["0924"]["mask"] & valid
    res["E1"] = {"pixels_both": int(both.sum()), "bias_m": round(float(diff.mean()), 3), "mad_m": round(float(np.abs(diff).mean()), 3),
                 "recall": round(float((ref & det).sum() / ref.sum()), 3), "iou": round(float((ref & det).sum() / (ref | det).sum()), 3)}

    # the polder P and the surfaces through time
    p_lab = overlap_part(sat["0924"]["labels"], g["ref_1001"])
    P = sat["0924"]["labels"] == p_lab
    gsurf, giqr = {}, {}
    for v in fb.VERSIONS:
        d = gsi[f"depth_{v}"]
        m = P & ~np.isnan(d)
        z = d[m] + dem[m]
        gsurf[v] = round(float(np.nanmedian(z)), 3)
        giqr[v] = round(float(np.subtract(*np.nanpercentile(z, [75, 25]))), 3)
    ssurf = {}
    for tag in ("0924", "1001", "1006"):
        k = overlap_part(sat[tag]["labels"], P)
        ssurf[tag] = round(float(sat[tag]["surf"][k]), 3) if k else None
    interp = gsurf["0924"] + (gsurf["0925"] - gsurf["0924"]) * (hours("s0924") - hours("0924")) / (hours("0925") - hours("0924"))
    res["polder"] = {"pixels": int(P.sum()), "gsi_surface_m": gsurf, "gsi_surface_iqr_m": giqr, "sat_surface_m": ssurf}
    res["E2"] = {"sat_0924_m": ssurf["0924"], "gsi_interp_0924_1741_m": round(float(interp), 3),
                 "diff_m": round(float(ssurf["0924"] - interp), 3) if ssurf["0924"] is not None else None}

    # E3: detection rate by GSI depth band
    has = valid & ~np.isnan(gd)
    res["E3"] = {}
    for lo, hi in BANDS:
        m = has & (gd >= lo) & (gd < hi)
        rate = float(sat["0924"]["mask"][m].mean()) if m.any() else None
        res["E3"][f"{lo}-{hi}"] = {"pixels": int(m.sum()), "rate": round(rate, 3) if rate is not None else None,
                                   "rate_pct": round(100 * rate, 1) if rate is not None else None}

    # E4: maximum depth
    stack = [gsi[f"depth_{v}"] for v in fb.VERSIONS] + [sat["0924"]["depth"], sat["1006"]["depth"]]
    with np.errstate(invalid="ignore"):
        mx = np.nanmax(np.stack(stack), axis=0)
        sat_only = np.nanmax(np.stack([np.nan_to_num(sat["0924"]["depth"]), np.nan_to_num(sat["1006"]["depth"])]), axis=0)
    flooded = ~water_perm & (np.nan_to_num(mx) > 0)
    res["E4"] = {"flooded_km2": km2(flooded.sum()), "max_depth_median_m": round(float(np.median(mx[flooded])), 3),
                 "max_minus_sat_only_median_m": round(float(np.median((mx - sat_only)[flooded])), 3),
                 "sat_only_median_m": round(float(np.median(sat_only[flooded])), 3)}

    # E5: the series
    res["E5"] = {"gsi_m": gsurf, "article_m": ARTICLE, "gsi_minus_article_m": {v: round(gsurf[v] - ARTICLE[v], 3) for v in ARTICLE},
                 "sat_1006_m": ssurf["1006"], "sat_1006_minus_gsi_1001_m": round(ssurf["1006"] - gsurf["1001"], 3) if ssurf["1006"] is not None else None}

    # E6: water left on 10-06 and the extrapolation
    union = g["ref_0922"] | g["ref_0924"] | g["ref_0925"] | g["ref_1001"]
    w6 = sat["1006"]["mask"] & union
    s_ext = extrapolate(hours("0925"), gsurf["0925"], hours("1001"), gsurf["1001"], hours("s1006"))
    pred = g["ref_1001"] & ~water_perm & (dem < s_ext)
    res["E6"] = {"sat_1006_in_union_km2": km2(w6.sum()), "share_in_1001_outline": round(float((w6 & g["ref_1001"]).sum() / w6.sum()), 3) if w6.any() else None,
                 "extrapolated_surface_m": round(float(s_ext), 3), "extrapolated_km2": km2(pred.sum())}

    # E7: mud on 10-01
    dried = g["ref_0925"] & ~g["ref_1001"] & ~water_perm
    res["E7"] = {"dried_km2": km2(dried.sum()), "called_water_km2": km2((dried & sat["1001"]["mask"]).sum())}
    return res, sat, mx


def judge(r):
    e3 = [r["E3"][f"{lo}-{hi}"]["rate"] for lo, hi in BANDS]
    c = {"D1": {"mad_le_0.35": r["E1"]["mad_m"] <= 0.35, "abs_bias_le_0.20": abs(r["E1"]["bias_m"]) <= 0.20},
         "D2": {"abs_diff_le_0.15": r["E2"]["diff_m"] is not None and abs(r["E2"]["diff_m"]) <= 0.15},
         "D3": {"increasing": all(a < b for a, b in zip(e3, e3[1:])), "shallowest_lt_0.50": e3[0] < 0.50, "deepest_ge_0.85": e3[-1] >= 0.85},
         "D4": {"median_diff_ge_0.30": r["E4"]["max_minus_sat_only_median_m"] >= 0.30},
         "D5": {"gsi_within_0.15": all(abs(v) <= 0.15 for v in r["E5"]["gsi_minus_article_m"].values()),
                "sat_1006_within_0.15": r["E5"]["sat_1006_minus_gsi_1001_m"] is not None and abs(r["E5"]["sat_1006_minus_gsi_1001_m"]) <= 0.15},
         "D6": {"area_ge_0.5": r["E6"]["sat_1006_in_union_km2"] >= 0.5, "share_ge_0.8": (r["E6"]["share_in_1001_outline"] or 0) >= 0.8,
                "extrapolated_le_half": r["E6"]["extrapolated_km2"] <= 0.5 * r["E6"]["sat_1006_in_union_km2"]},
         "D7": {"called_water_ge_0.2": r["E7"]["called_water_km2"] >= 0.2}}
    return {k: {"conditions": {n: bool(x) for n, x in v.items()}, "reproduced": bool(all(v.values()))} for k, v in c.items()}


def main():
    g = dict(np.load(fb.ART / "grid.npz"))
    w = dict(np.load(fb.ART / "water_b.npz"))
    gsi = dict(np.load(fb.ART / "gsi_depth.npz"))
    res, sat, mx = analyse(g, w, gsi)
    out = {"main": res, "judgement": judge(res), "variants": {}}
    np.savez_compressed(fb.ART / "depth_b.npz", sat_0924=sat["0924"]["depth"].astype(np.float32),
                        sat_1001=sat["1001"]["depth"].astype(np.float32), sat_1006=sat["1006"]["depth"].astype(np.float32),
                        max_depth=mx.astype(np.float32))
    variants = {"water_rtc": ({**w, "w0924": w["w0924_rtc"], "w1001": w["w1001_rtc"]}, gsi, {}),
                "water_0924_vv": ({**w, "w0924": w["w0924_vv"]}, gsi, {}),
                "surface_0924_q95": (w, gsi, {"q0924": 0.95}),
                "surface_0924_iou": (w, gsi, {"rule0924": "iou"})}
    d5 = fb.ART / "gsi_depth_d5.npz"
    if d5.exists():
        variants["gsi_max_dist_5"] = (w, dict(np.load(d5)), {})
    for name, (wv, gv, kw) in variants.items():
        rv = analyse(g, wv, gv, **kw)[0]
        out["variants"][name] = {"E1": rv["E1"], "E2": rv["E2"], "E3": rv["E3"], "E4": rv["E4"],
                                 "judgement": {k: v["reproduced"] for k, v in judge(rv).items()}}
    (OUT / "blocks_b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"main": res, "judgement": {k: v["reproduced"] for k, v in out["judgement"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Exploratory checks made after the confirmatory results (not in EXPERIMENT_PLAN.md). Writes outputs/explore.json.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with scikit-image --with pyproj python -u scripts/05_explore.py

1. placebo: orbit 46 with the last pre scene (2019-10-06) in place of the event and the five earlier pre scenes as the
   pre mean; B0 to B3 with the main settings. A brightening of the recorded built-up pixels that also shows here is
   not the flood.
2. return of the brightening: of the REC built-up pixels (and CTRL built-up) that brightened by 3 dB or more on
   10-13, the share whose dVV (same pre mean, 3 x 3) is below +1.5 dB on 10-18 and on 10-30.
3. by municipality: the brightened share of REC built-up pixels on 10-13, and on the placebo pair.
"""
import importlib.util
import json

import numpy as np

import flood
from common import ART, HERE, OUT, SCENES

spec = importlib.util.spec_from_file_location("blocks", HERE / "03_blocks.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def main():
    aux = dict(np.load(ART / "aux.npz"))
    t = aux["transform"]
    rr, cc = np.mgrid[0:aux["wc"].shape[0], 0:aux["wc"].shape[1]]
    aux["x"], aux["y"] = t[2] + (cc + 0.5) * t[0], t[5] + (rr + 0.5) * t[4]
    gsum = json.loads((OUT / "grid_summary.json").read_text(encoding="utf-8"))
    shift = gsum["orbits"]["46"]["shift_back"]
    st = np.load(ART / "stack_o46.npy", mmap_mode="r")
    dates = [d for _, d in SCENES[46]]
    pre = [i for i, (r, _) in enumerate(SCENES[46]) if r == "pre"]

    def img(k, idx):
        a = np.asarray(st[k, idx], float)
        a = np.nanmean(a, axis=0) if a.ndim == 3 else a
        return flood.apply_int_shift(a, shift) if any(shift) else a

    def delta(post_idx, pre_idx):
        return {p: flood.ratio_db(flood.boxcar(img(k, post_idx), 3), flood.boxcar(img(k, pre_idx), 3))
                for k, p in enumerate(("vv", "vh"))}

    out = {"note": "exploratory, after the confirmatory results"}
    dp = delta(pre[-1], pre[:-1])
    dp["vv_after"] = dp["vv"]
    m, g, dark_p, bright_p = B.evaluate(aux, dp)
    out["placebo_2019-10-06"] = {k: m[k] for k in ("B0", "B1", "B2", "B3", "ctrl_median_db")}
    out["placebo_2019-10-06"]["decisions"] = B.decide(m)

    dm = delta(dates.index("2019-10-12"), pre)
    m2, g2, dark, bright = B.evaluate(aux, dm)
    b50 = aux["wc"] == 50
    out["return_of_brightening"] = {}
    for name in ("2019-10-18", "2019-10-30"):
        da = delta(dates.index(name), pre)["vv"]
        r = {}
        for grp in ("REC", "CTRL", "A31A"):
            sel = bright & g2[grp] & b50 & np.isfinite(da)
            r[grp] = {"bright_pixels": int(sel.sum()), "share_back_below_1.5db": round(float((da[sel] < 1.5).mean()), 4),
                      "median_db_then": round(float(np.median(da[sel])), 3)}
        out["return_of_brightening"][name] = r
    rows = {}
    for code in np.unique(aux["ward"][g2["REC"]]):
        mm = g2["REC"] & b50 & (aux["ward"] == code)
        rows[int(code)] = {"rec_built_pixels": int(mm.sum()), "bright_share": round(float(bright[mm].mean()), 4),
                           "bright_share_placebo": round(float(bright_p[mm].mean()), 4)}
    out["rec_built_bright_by_municipality"] = rows
    (OUT / "explore.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

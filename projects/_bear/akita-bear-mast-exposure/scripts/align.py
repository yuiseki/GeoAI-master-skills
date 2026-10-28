"""B0: align the saved B_env surfaces with the labels and check that the bear project's numbers come back
(capture@5% of B_env and the positive cell counts). Stops if they do not.

    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-mast-exposure/scripts \
      uvx --with numpy --with pandas --with pyarrow python align.py BEAR_ART ART MAST_CSV OUT_JSON
"""

import json
import sys

import numpy as np

import data
import metrics as mt

EXPECT_CAPTURE = {2024: 0.5341823056300268, 2025: 0.5515891508994315, 2026: 0.5391963109354414}
EXPECT_POS = {2023: 3439, 2024: 1492, 2025: 10729, 2026: 3036}


def main():
    bear, art, mast_csv, out = sys.argv[1:5]
    d = data.load(bear, art)
    res = {"inputs": {f: data.sha256(f"{bear}/{f}") for f in ("grid.json", "grid_mask.npz", "cells.parquet", "reports_by_year.npz")}
           | {f"eval/{f}_scores.npz": data.sha256(f"{bear}/eval/{f}_scores.npz") for f in data.SURFACE.values()}
           | {"exposure.npz": data.sha256(f"{art}/exposure.npz"), "mast_csv": data.sha256(mast_csv)}}
    n = len(d["blocks"])
    res["cells"] = n
    res["blocks_10km"] = int(len(np.unique(d["blocks"])))
    res["positive_cells"] = {t: int((c > 0).sum()) for t, c in d["counts"].items()}
    res["reports"] = {t: int(c.sum()) for t, c in d["counts"].items()}
    ok = all(res["positive_cells"][t] == v for t, v in EXPECT_POS.items())
    res["b_env_capture@5%"] = {}
    for t, s in d["benv"].items():
        assert len(s) == n
        c = mt.capture(mt.rank_order(s), d["counts"][t] > 0, 0.05)
        res["b_env_capture@5%"][t] = {"got": c, "expect": EXPECT_CAPTURE[t], "match": abs(c - EXPECT_CAPTURE[t]) < 1e-9}
        ok &= abs(c - EXPECT_CAPTURE[t]) < 1e-9
    res["mast_scarcity"] = {"fruiting": data.read_mast(mast_csv, "fruiting"), "flowering": data.read_mast(mast_csv, "flowering")}
    res["mast_scarcity"] = {k: {y: v[y] for y in (2023, 2024, 2025, 2026)} for k, v in res["mast_scarcity"].items()}
    nan = {}
    for f in d["exposure"].files:
        if "fraction" in f:
            _, nan[f] = data.exposure_vec(d["exposure"], f, d["muni"])
    res["exposure_nan_set_to_zero"] = nan
    res["all_match"] = bool(ok)
    json.dump(res, open(out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if not ok:
        raise SystemExit("the saved B_env or the labels do not reproduce the bear project")


if __name__ == "__main__":
    main()

"""Exploratory (added after stage A was judged): stage A's blocks and judgement again, with the scenes of 2026-09-12
and 09-24 from our GRD processing instead of the RTC scenes, which lie about 2 pixels off the WorldCover water
(outputs/grd_check.json).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with scipy --with shapely --with pyproj python scripts/13_stage_a_grd.py

Writes outputs/blocks_a_grd.json. The planned judgement of stage A (outputs/blocks.json) is not changed.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
cmp = __import__("04_compare")
from sar import detect  # noqa: E402

ART = cmp.ART


def main():
    g = dict(np.load(ART / "grid.npz"))
    b, a = np.load(ART / "grd_0912.npz"), np.load(ART / "grd_0924.npz")
    gg = {**g, "vv_b": b["vv"], "vh_b": b["vh"], "vv_a": a["vv"], "vh_a": a["vh"]}
    r = detect(gg["vv_b"], gg["vh_b"], gg["vv_a"], gg["vh_a"], g["dem"], g["water"])
    win = np.load(ART / "windows.npz")["buffer"]
    valid = win & ~g["water"] & r["ok"]
    core = g["ref_1001"] & ~g["water"] & r["ok"]
    blocks = cmp.blocks(gg, r, valid, core)
    out = {"fit": r["fit"], "main": blocks, "judgement": cmp.judge(blocks)}
    (HERE.parent / "outputs/blocks_a_grd.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"B1": blocks["B1"], "B2": blocks["B2"], "B3": blocks["B3"], "B5": blocks["B5"],
                      "judgement": {k: v["reproduced"] for k, v in out["judgement"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

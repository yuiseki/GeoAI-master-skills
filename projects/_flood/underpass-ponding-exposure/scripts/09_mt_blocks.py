"""The Mapterhorn z16 depth set beside the plan's blocks (exploratory, added after the results).

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas python scripts/09_mt_blocks.py

Reads measures_mt.parquet (04_profile.py --with-mt, the plan's endpoint chain) and writes outputs/blocks_mt.json:
- B1: the share with a dip of 2 m or more on Mapterhorn, and a table of which points DEM5A and Mapterhorn show as dips;
- B2: the overlap of the top 10% on Mapterhorn with the plan's main score;
- B3, B4: the AUCs of the Mapterhorn depth, by the same rules as 05_blocks.py.
Both depth rules (bottom within 30 m, and within L) are reported.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("blocks", HERE / "05_blocks.py")
bl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bl)


def crosstab(rows, prefix, thresh=2.0):
    a = bl.measurable(rows, f"{prefix}_5a_100")
    b = bl.measurable(rows, f"{prefix}_mt_100")
    both = a & b
    d5 = rows[f"{prefix}_5a_100"] >= thresh
    dm = rows[f"{prefix}_mt_100"] >= thresh
    return {"measurable_both": int(both.sum()), "dip_both": int((both & d5 & dm).sum()),
            "dip_5a_only": int((both & d5 & ~dm).sum()), "dip_mt_only": int((both & ~d5 & dm).sum()),
            "dip_neither": int((both & ~d5 & ~dm).sum()),
            "mt_measurable_where_5a_not": int((rows["matched"] & ~a & b).sum()),
            "mt_dip_where_5a_not_measurable": int((rows["matched"] & ~a & b & dm).sum())}


def main():
    rows = bl.load(str(bl.ART / "measures_mt.parquet"), 30)
    n_all = len(rows)
    res = {}
    for prefix in ("depth", "depthw"):
        rng = np.random.default_rng(0)
        bl.MAIN, bl.VARIANTS = f"{prefix}_mt_100", {"plan_main": f"{prefix}_mix_100", "dem5a": f"{prefix}_5a_100"}
        r = {"B1": bl.b1(rows, 2.0, n_all), "crosstab": crosstab(rows, prefix), "B2": bl.b2(rows, 0.10, rng),
             "B3": bl.b3(rows, rng, dist=30), "B4": bl.b4(rows, rng),
             "B4_text_records_only": bl.b4(rows, rng, label="rec_text")}
        m = bl.measurable(rows, f"{prefix}_mt_100")
        r["B1"]["mt_dip_only_away_from_point"] = int((m & (rows["depth_mt_100"] < 2) & (rows["depthw_mt_100"] >= 2)).sum())
        res[prefix] = r
    out = HERE.parent / "outputs/blocks_mt.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\n")
    print(json.dumps({p: res[p]["crosstab"] for p in res}, ensure_ascii=False))


if __name__ == "__main__":
    main()

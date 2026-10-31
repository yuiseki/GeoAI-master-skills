"""Blocks B1 to B4 of EXPERIMENT_PLAN.md, the planned judgement of C1 to C3, and the robustness rows.

uvx --with numpy --with pandas --with pyarrow python scripts/02_blocks.py

Writes outputs/blocks.json and outputs/b4_by_kind.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from listing import block_bootstrap, diff_share, grid_blocks, share, verdict, verdict_below

HERE = Path(__file__).resolve().parent
ART = HERE.parents[3] / "artifacts/_flood/tokyo23-underpass-listing"
OUT = HERE.parent / "outputs"


def load(pop):
    return pd.read_parquet(ART / f"units_{pop}.parquet")


def blocks_for(u, d=100.0, flood="flood"):
    listed = (u["d_list"] <= d).to_numpy()
    fl = u[flood].to_numpy(bool)
    b = grid_blocks(u["x"], u["y"])
    r = {"units": int(len(u)), "listed": int(listed.sum()), "flood": int(fl.sum()), "flood_listed": int((fl & listed).sum()),
         "flood_unlisted": int((fl & ~listed).sum()), "blocks": int(len(np.unique(b)))}
    r["B1_share_listed"] = round(share(listed), 3)
    lo, hi, _ = block_bootstrap(b, lambda i: share(listed[i]))
    r["B1_ci"] = [round(lo, 3), round(hi, 3)]
    r["B2_flood_share_listed"] = round(share(fl[listed]), 3)
    r["B2_flood_share_unlisted"] = round(share(fl[~listed]), 3)
    r["B2_diff"] = round(diff_share(fl, listed), 3)
    lo2, hi2, n2 = block_bootstrap(b, lambda i: diff_share(fl[i], listed[i]))
    r["B2_ci"] = [round(lo2, 3), round(hi2, 3)]
    r["B3_unlisted_share_of_flood"] = round(share(~listed[fl]), 3) if fl.any() else None
    lo3, hi3, n3 = block_bootstrap(b, lambda i: share(~listed[i][fl[i]]) if fl[i].any() else np.nan)
    r["B3_ci"] = [round(lo3, 3), round(hi3, 3)]
    r["bootstrap_used"] = {"B2": n2, "B3": n3}
    r["verdict"] = {"C1": verdict_below(*r["B1_ci"], 0.5), "C2": verdict(*r["B2_ci"], 0.0), "C3": verdict(*r["B3_ci"], 0.2)}
    for k in ("B1_share_listed", "B2_flood_share_listed", "B2_flood_share_unlisted", "B3_unlisted_share_of_flood"):
        if r[k] is not None:
            r[k + "_pct"] = round(100 * r[k], 1)
    return r


def b4(u):
    u = u.copy()
    u["listed"] = u["d_list"] <= 100
    u["kansui"] = u["d_kansui"] <= 100
    u["length"] = pd.qcut(u["len_m"], 3, labels=["short", "middle", "long"])
    rows = []
    for col in ("road_class", "form", "length"):
        for v, g in u.groupby(col, observed=True):
            rows.append({"by": col, "value": str(v), "units": len(g), "listed": int(g["listed"].sum()),
                         "listed_share": round(g["listed"].mean(), 3), "kansui": int(g["kansui"].sum()),
                         "kansui_share": round(g["kansui"].mean(), 3), "flood": int(g["flood"].sum()),
                         "len_m_median": round(float(g["len_m"].median()), 1)})
    return pd.DataFrame(rows)


def main():
    main_u = load("main")
    out = {"main": blocks_for(main_u), "variants": {}}
    out["variants"]["d_50"] = blocks_for(main_u, d=50)
    out["variants"]["d_200"] = blocks_for(main_u, d=200)
    out["variants"]["flood_30m"] = blocks_for(main_u, flood="flood30")
    out["variants"]["flood_naisui"] = blocks_for(main_u, flood="flood_naisui")
    out["variants"]["service"] = blocks_for(load("service"))
    out["variants"]["guard"] = blocks_for(load("guard"))
    k = main_u["d_kansui"] <= 100
    out["kansui"] = {"units_with_kansui_100m": int(k.sum()), "share": round(float(k.mean()), 3),
                     "both_list_and_kansui": int((k & (main_u["d_list"] <= 100)).sum())}
    t = b4(main_u)
    t.to_csv(OUT / "b4_by_kind.csv", index=False)
    (OUT / "blocks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["main"], ensure_ascii=False))
    for name, v in out["variants"].items():
        print(name, v["units"], v["B1_share_listed"], v["B1_ci"], v["B2_diff"], v["B2_ci"], v["B3_unlisted_share_of_flood"], v["B3_ci"], v["verdict"])
    print(out["kansui"])
    print(t.to_string())


if __name__ == "__main__":
    main()

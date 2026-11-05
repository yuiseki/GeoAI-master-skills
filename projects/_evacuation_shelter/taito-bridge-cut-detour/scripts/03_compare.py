"""Compare the variants against main (B4) and sum the worst-case increments by what the structure crosses (B3).

uvx --with pandas --with numpy --with scipy --with pyarrow python scripts/03_compare.py

Writes outputs/robustness.csv, outputs/crossing_kinds.csv, outputs/compare_summary.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

OUT = Path(__file__).resolve().parent.parent / "outputs"
ART = Path(__file__).resolve().parents[4] / "artifacts/_evacuation_shelter/taito-bridge-cut-detour"
RULE_VARIANTS = ["cluster5", "cluster20", "sites_taito", "corridor", "buffer3000", "buffer8000"]
DESCRIBE_ONLY = ["tunnels"]
TOP = 5


def load(v):
    c = pd.read_csv(OUT / v / "cells.csv", dtype={"cell": str})
    s = json.loads((OUT / v / "summary.json").read_text(encoding="utf-8"))
    st = pd.read_csv(OUT / v / "structures.csv") if (OUT / v / "structures.csv").stat().st_size > 1 else pd.DataFrame()
    return c, s, st


def main():
    mc, ms, mst = load("main")
    m_top = list(mc.cell[:TOP])
    n_pos_main = int((mc.inc_median_m > 0).sum())
    rows = []
    for v in ["main"] + RULE_VARIANTS + DESCRIBE_ONLY:
        c, s, st = load(v)
        top = list(c.cell[:TOP])
        j = mc.merge(c, on="cell", suffixes=("_m", "_v"))
        rho = spearmanr(j.inc_median_m_m, j.inc_median_m_v).statistic if j.inc_median_m_v.nunique() > 1 else np.nan
        rho_max = spearmanr(j.inc_max_m_m, j.inc_max_m_v).statistic
        r = s["results"]
        rows.append(dict(variant=v, in_rule=v in RULE_VARIANTS, top5=" ".join(top), top5_common=len(set(top) & set(m_top)),
                         cells_median_gt0=int((c.inc_median_m > 0).sum()),
                         spearman_median=None if np.isnan(rho) else round(float(rho), 3),
                         spearman_max=round(float(rho_max), 3),
                         share_lengthened=r["share_lengthened"], share_unreachable=r["share_unreachable"],
                         share_inc_ge500=r["share_inc_ge500"], inc_max_m=round(float(c.inc_max_m.replace(np.inf, np.nan).max()), 1),
                         n_inf_cells=int(np.isinf(c.inc_max_m).sum()),
                         structures_lengthening=s["structures"]["groups_lengthening"],
                         top_structure=(st.sort_values("inc_sum_m", ascending=False).name.fillna("").iloc[0] if len(st) else ""),
                         sites=s["sites"]["n"], d0_median_m=r["d0_median_m"]))
    rob = pd.DataFrame(rows)
    rob.to_csv(OUT / "robustness.csv", index=False, encoding="utf-8")

    # B3: the main run, by crossing kind; a structure crossing both counts in both
    k = mst.copy()
    k["kinds"] = k.kinds.str.split("+")
    k = k.explode("kinds")
    kinds = k.groupby("kinds").agg(structures=("struct", "size"), origins_worst=("n_origins_worst", "sum"),
                                   inc_sum_m=("inc_sum_m", "sum"), inc_max_m=("inc_max_m", "max"),
                                   n_inc_ge500=("n_inc_ge500", "sum")).reset_index()
    kinds.to_csv(OUT / "crossing_kinds.csv", index=False, encoding="utf-8")
    rail = float(kinds.loc[kinds.kinds == "rail", "inc_sum_m"].sum())
    river = float(kinds.loc[kinds.kinds == "river", "inc_sum_m"].sum())
    tot = max(rail, river)
    c2 = "support" if rail > river and (rail - river) > 0.1 * tot else \
         "reject" if river > rail and (river - rail) > 0.1 * tot else "undecided"

    # unit check: the same origins summarised by 1 km mesh (the parent of the 500 m cell)
    o = pd.read_parquet(ART / "main" / "origins.parquet")
    o = o[o.used].copy()
    o["mesh1km"] = o.cell.str[:8]
    unit = []
    for col, name in [("cell", "500m"), ("mesh1km", "1km")]:
        gb = o.groupby(col)
        t = pd.DataFrame({"n_points": gb.size(), "inc_median_m": gb.inc.median(), "inc_max_m": gb.inc.max(),
                          "share_lengthened": gb.struct.apply(lambda s: float((s >= 0).mean()))}).reset_index()
        t = t.rename(columns={col: "unit_id"})
        t["unit"] = name
        unit.append(t.sort_values(["inc_median_m", "inc_max_m"], ascending=False))
    unit = pd.concat(unit)
    unit.to_csv(OUT / "unit_500m_vs_1km.csv", index=False, encoding="utf-8")

    rule_rows = rob[rob.in_rule]
    c1 = "support" if (rule_rows.top5_common >= 3).all() else "reject"
    summary = dict(top_n=TOP, main_top5=m_top, main_cells_median_gt0=n_pos_main,
                   C1=dict(rule="top-5 overlap >= 3 in all of " + ", ".join(RULE_VARIANTS), verdict=c1,
                           overlaps=dict(zip(rule_rows.variant, rule_rows.top5_common.astype(int)))),
                   C2=dict(rule="rail inc_sum > river inc_sum by more than 10%", rail_inc_sum_m=round(rail, 1),
                           river_inc_sum_m=round(river, 1), verdict=c2))
    (OUT / "compare_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(rob.drop(columns=["top5"]).to_string())
    print(kinds.to_string())
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

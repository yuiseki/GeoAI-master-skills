"""B5 (exploratory, after the confirmation; not used for the verdict): where the positives fall by beech/oak
exposure class and by region, 2023-2026, and how often B_env's top 5% misses them.

Classes of the frozen exposure: Q0 = 0, Q1-Q4 = quartiles of the positive values over all prefecture cells
(edges computed once). B_env surface per year: the one that targets that year (2023: the b1 surface, in-sample).

    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-mast-exposure/scripts \
      uvx --with numpy --with pandas --with pyarrow python diagnose.py BEAR_ART ART MAST_CSV OUTDIR
"""

import json
import math
import sys

import numpy as np

REGIONS = {
    "秋田市": ["秋田市"],
    "県北": ["鹿角市", "小坂町", "大館市", "北秋田市", "上小阿仁村", "能代市", "藤里町", "三種町", "八峰町"],
    "中央 (秋田市を除く)": ["男鹿市", "潟上市", "五城目町", "八郎潟町", "井川町", "大潟村", "由利本荘市", "にかほ市"],
    "県南": ["大仙市", "仙北市", "美郷町", "横手市", "湯沢市", "羽後町", "東成瀬村"],
}
SURF_FOR = {2023: 2024, 2024: 2024, 2025: 2025, 2026: 2026}


def class_edges(e):
    return np.quantile(e[e > 0], [0.25, 0.5, 0.75]).tolist()


def classes(e, edges):
    k = np.zeros(len(e), dtype=int)
    pos = e > 0
    k[pos] = 1 + np.searchsorted(edges, e[pos], side="left")
    return k


def top_mask(score, k):
    import metrics as mt

    n = math.ceil(k * len(score))
    m = np.zeros(len(score), bool)
    m[mt.rank_order(score)[:n]] = True
    return m


def qs(v):
    return {"n": int(v.size), "mean": float(v.mean()), "q25": float(np.quantile(v, 0.25)), "median": float(np.median(v)), "q75": float(np.quantile(v, 0.75))}


def main():
    import data

    bear, art, mast_csv, outdir = sys.argv[1:5]
    spec = json.load(open(f"{outdir}/b1_frozen_spec.json"))
    d = data.load(bear, art)
    names = json.load(open(f"{bear}/grid.json"))["names"]
    e, _ = data.exposure_vec(d["exposure"], spec["features"]["M5"], d["muni"])
    edges = class_edges(e)
    k = classes(e, edges)
    muni = data.vec(d["muni"], d["muni"])
    region = np.empty(len(e), dtype=object)
    for r, ms in REGIONS.items():
        region[np.isin(muni, [names.index(m) for m in ms])] = r
    s = data.read_mast(mast_csv, "fruiting")
    res = {"feature": spec["features"]["M5"], "class_edges": edges, "class_cells": np.bincount(k).tolist(), "by_year": {}, "regions": {}}
    for t in (2023, 2024, 2025, 2026):
        y = d["counts"][t] > 0
        top = top_mask(d["benv"][SURF_FOR[t]], 0.05)
        rows = []
        for q in range(5):
            m = k == q
            rows.append({"class": f"Q{q}", "cells": int(m.sum()), "positives": int(y[m].sum()), "positive_rate": float(y[m].mean()),
                         "share_of_positives": float(y[m].sum() / y.sum()),
                         "b_env_miss_rate": float((y & m & ~top).sum() / max(1, (y & m).sum())),
                         "share_of_top5": float((top & m).sum() / top.sum())})
        res["by_year"][t] = {"mast_scarcity": s[t], "b_env_surface": data.SURFACE[SURF_FOR[t]], "positives": int(y.sum()),
                             "exposure_of_positives": qs(e[y]), "exposure_of_all": qs(e), "classes": rows,
                             "by_region": {r: {"positives": int((y & (region == r)).sum()),
                                               "exposure_of_positives": qs(e[y & (region == r)]) if (y & (region == r)).any() else None}
                                           for r in REGIONS}}
    for r in REGIONS:
        m = region == r
        res["regions"][r] = {"cells": int(m.sum()), "exposure": qs(e[m]), "class_share": (np.bincount(k[m], minlength=5) / m.sum()).tolist()}
    json.dump(res, open(f"{outdir}/b5_diagnostics.json", "w"), indent=1, ensure_ascii=False)
    for t, v in res["by_year"].items():
        print(t, v["mast_scarcity"], v["positives"], round(v["exposure_of_positives"]["mean"], 3),
              [(c["class"], round(c["positive_rate"] * 1000, 2), round(c["b_env_miss_rate"], 2)) for c in v["classes"]])


if __name__ == "__main__":
    main()

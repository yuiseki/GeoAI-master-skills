"""Exploratory checks after the transfer results (plan: E1, E2). Writes one table per region for score_risk_map.py.

E1  The bear range: the 10 km blocks with any report in the first half of the region's period. The later half's
    reports are the labels. Scores: AK, AK_range (AK, with cells outside the range put last), H1 (first-half reports
    within about 1 km, a history map), B_pop. The table has `in_range` so it can also be scored inside the range only.
E2  AK_nobldg: the Akita model refitted without the OSM building features (d_building, bldg_500), scored on the
    whole period's labels like AK.

Usage:
    ... python explore.py AKITA_ART OUT_DIR REGION_ART:FIRST_LAST:SECOND_FIRST [...]
    e.g. artifacts/_bear/bear-risk-transfer/gifu:2019:2020 (first half up to 2019, second half from 2020)
"""

import os
import sys

import numpy as np

import features as ft
from transfer_eval import HGB, static_table

DROP = ("d_building", "bldg_500")


def main():
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier

    akita, out = sys.argv[1], sys.argv[2]
    Xa, names, inside_a = static_table(akita)
    rep = np.load(f"{akita}/reports_by_year.npz")
    ya = np.concatenate([(rep[f"c{y}"][inside_a] > 0) for y in (2023, 2024, 2025)])
    full = HistGradientBoostingClassifier(**HGB, random_state=0).fit(np.vstack([Xa] * 3), ya)
    keep = [j for j, n in enumerate(names) if n not in DROP]
    nob = HistGradientBoostingClassifier(**HGB, random_state=0).fit(np.vstack([Xa[:, keep]] * 3), ya)
    for spec in sys.argv[3:]:
        art, first_last, second_first = spec.split(":")
        first_last, second_first = int(first_last), int(second_first)
        region = os.path.basename(art.rstrip("/"))
        X, n2, inside = static_table(art)
        cells = pd.read_parquet(f"{art}/cells.parquet", columns=["cell", "ix", "iy"])
        r = np.load(f"{art}/reports.npz")
        periods = sorted(int(k[1:]) for k in r.files if k.startswith("p") and int(k[1:]) > 0)
        first = sum(r[f"p{p}"] for p in periods if p <= first_last)
        second = sum(r[f"p{p}"] for p in periods if p >= second_first)
        blocks = (cells.ix.to_numpy() // 100) * 100000 + cells.iy.to_numpy() // 100
        fb = pd.Series(first[inside] > 0).groupby(blocks).any()
        in_range = pd.Series(blocks).map(fb).to_numpy()
        ak = full.predict_proba(X)[:, 1]
        h1 = ft.box_sum(first.astype(float), 10)[inside]
        tab = pd.DataFrame({"cell": cells.cell, "ix": cells.ix, "iy": cells.iy, "block": blocks,
                            "label2": second[inside], "label": r["total"][inside], "in_range": in_range,
                            "AK": ak, "AK_range": np.where(in_range, ak, -1.0 + ak), "H1": h1,
                            "B_pop": X[:, names.index("pop_500")], "B_pop2": X[:, names.index("pop_2000")],
                            "AK_nobldg": nob.predict_proba(X[:, keep])[:, 1]})
        tab.to_parquet(f"{out}/{region}_explore.parquet")
        tab[tab.in_range].to_parquet(f"{out}/{region}_explore_inrange.parquet")
        n1 = int(sum(r[f"p{p}"].sum() for p in periods if p <= first_last))
        n2 = int(sum(r[f"p{p}"].sum() for p in periods if p >= second_first))
        print(f"{region}: first half (<= {first_last}) {n1} reports, second half (>= {second_first}) {n2}; range blocks "
              f"{int(fb.sum())} of {len(fb)}, range cells {int(in_range.sum())} of {len(in_range)}; second-half positive cells "
              f"{int((tab.label2 > 0).sum())}, of them in the range {int(((tab.label2 > 0) & tab.in_range).sum())}")


if __name__ == "__main__":
    main()

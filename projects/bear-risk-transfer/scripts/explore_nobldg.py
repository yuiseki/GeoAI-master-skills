"""Exploratory: the cost in Akita of leaving out the OSM building features, and that model limited to the range.

Fits the no-building model on Akita's bear years 2023-2025 (as the map model) and scores Akita's 2026 (April to
September) like block B3; adds AK_nobldg_range to each region's explore table (cells outside the range put last).

Usage:
    ... python explore_nobldg.py AKITA_ART OUT_DIR REGION [REGION ...]
"""

import sys

import numpy as np
import pandas as pd

from explore import DROP
from transfer_eval import HGB, static_table


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier

    akita, out = sys.argv[1], sys.argv[2]
    Xa, names, inside = static_table(akita)
    rep = np.load(f"{akita}/reports_by_year.npz")
    ya = np.concatenate([(rep[f"c{y}"][inside] > 0) for y in (2023, 2024, 2025)])
    keep = [j for j, n in enumerate(names) if n not in DROP]
    nob = HistGradientBoostingClassifier(**HGB, random_state=0).fit(np.vstack([Xa[:, keep]] * 3), ya)
    cells = pd.read_parquet(f"{akita}/cells.parquet", columns=["cell", "ix", "iy"])
    full_b3 = np.load(f"{akita}/eval/b3_confirm_2023-2025_to_2026_scores.npz")["B_env"]
    pd.DataFrame({"cell": cells.cell, "ix": cells.ix, "iy": cells.iy,
                  "block": (cells.ix // 100) * 10000 + cells.iy // 100,
                  "label": rep["c2026"][inside], "AK": full_b3, "AK_nobldg": nob.predict_proba(Xa[:, keep])[:, 1]}
                 ).to_parquet(f"{out}/akita_nobldg.parquet")
    for region in sys.argv[3:]:
        t = pd.read_parquet(f"{out}/{region}_explore.parquet")
        t["AK_nobldg_range"] = np.where(t.in_range, t.AK_nobldg, -1.0 + t.AK_nobldg)
        t.to_parquet(f"{out}/{region}_explore.parquet")
    print("written")


if __name__ == "__main__":
    main()

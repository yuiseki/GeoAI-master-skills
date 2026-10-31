"""Place every 100 m cell in the phase space (bear-side percentile, human-side percentile) and count, per year,
the positive cells in each of the 25 bins and 6 preregistered regions.

Each year is placed with M_B and M_H fitted without that year: 2024 with the B1 models (trained on 2023), 2025 with
B2 (2023+2024), 2026 with B3 (2023-2025), and 2023, which has no earlier year, with the models trained on 2024+2025
(backward; marked in the output). Positive cells: April-September (main, same season every year) and the whole
bear year (2023-2025; 2026 has only April-September).

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_phase_space.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface \
      projects/_bear/akita-bear-human-interface/outputs/phase_space.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import interface_models as im
import phase as ph

YEAR_AXIS = {2023: ("axes_2024-2025.npz", "backward: trained on 2024+2025"),
             2024: ("b1_dev_2023_to_2024.npz", "forward: B1, trained on 2023"),
             2025: ("b2_confirm_2023-2024_to_2025.npz", "forward: B2, trained on 2023+2024"),
             2026: ("b3_confirm_2023-2025_to_2026.npz", "forward: B3, trained on 2023-2025")}


def axes(path):
    z = np.load(path)
    return ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))


def positives(art, work, inside):
    season = np.load(Path(work) / "labels/season_counts.npz")
    full = np.load(Path(art) / "reports_by_year.npz")
    out = {"apr_sep": {y: season[f"s{y}"][inside] > 0 for y in YEAR_AXIS},
           "bear_year": {y: full[f"c{y}"][inside] > 0 for y in YEAR_AXIS if y < 2026}}
    return out


def main():
    from scipy.stats import spearmanr

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    args = a.parse_args()
    im.check_inputs(args.art)
    inside = np.load(args.art / "grid_mask.npz")["muni"] >= 0
    pos = positives(args.art, args.work, inside)
    res = {"derived": "bins of model scores; the axes are proxies, not bear or human densities",
           "regions": {r: sorted([b, h] for b in range(1, 6) for h in range(1, 6) if ph.region(b, h) == r)
                       for r in ph.REGIONS},
           "years": {}}
    for y, (f, note) in YEAR_AXIS.items():
        p = args.work / "scores" / f
        pb, phh = axes(p)
        bq, hq = ph.quintile(pb), ph.quintile(phh)
        row = {"axis": f, "axis_sha256": im.sha256(p), "axis_note": note,
               "spearman_b_h_all_cells": float(spearmanr(pb, phh).statistic)}
        for kind, d in pos.items():
            if y not in d:
                continue
            m = d[y]
            row[kind] = {"n_pos": int(m.sum()), "bins": ph.bin_table(bq, hq, m), "regions": ph.region_table(bq, hq, m),
                         "b_pct": ph.summary(pb[m]), "h_pct": ph.summary(phh[m]),
                         "jsd_pos_vs_cells": ph.jsd(ph.bin_counts(bq, hq, m), ph.bin_counts(bq, hq, np.ones_like(m)))}
        res["years"][str(y)] = row
        r = row["apr_sep"]["regions"]
        print(y, note, "spearman", round(row["spearman_b_h_all_cells"], 3), "| apr-sep n", row["apr_sep"]["n_pos"],
              {k: (round(v["share"], 3), round(v["lift"], 2)) for k, v in r.items()})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()

"""What the existing data say about the reporting process (hypothesis D), April-September of 2023-2026.

Reuses R040 (municipality and info_type shares, 2024-2026) and R039 (feature shifts of positive cells, 2024-2025 and
2025-2026) of akita-bear-risk-grid-100m: their numbers are checked against the ones rebuilt here and not reported
twice. Added: 2023, the 2023 -> 2024 comparisons, the number of reports per positive cell, and the reports and their
info_type by human-side quintile (each year on the axis of interface_phase_space.YEAR_AXIS).

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_reporting.py artifacts/_bear/akita-bear-risk-grid-100m \
      artifacts/_bear/akita-bear-human-interface projects/_bear/akita-bear-human-interface/outputs/reporting_process.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import interface_models as im
import phase as ph
from interface_phase_space import YEAR_AXIS

YEARS = (2023, 2024, 2025, 2026)
PAIRS = ((2023, 2024), (2024, 2025), (2025, 2026))
GRID = Path(__file__).resolve().parents[2] / "akita-bear-risk-grid-100m/outputs"
TOL = 1e-9


def shares(values):
    u, n = np.unique(np.asarray(values), return_counts=True)
    return {str(k): int(v) for k, v in zip(u, n)}


def as_share(counts):
    t = sum(counts.values())
    return {k: v / t for k, v in counts.items()}


def jsd_dict(a, b):
    keys = sorted(set(a) | set(b))
    return ph.jsd([a.get(k, 0) for k in keys], [b.get(k, 0) for k in keys])


def per_cell(cells):
    """Reports per positive cell: mean, and the share of positive cells with two or more."""
    n = np.bincount(cells)
    n = n[n > 0]
    return {"positive_cells": int(len(n)), "reports": int(n.sum()), "reports_per_cell": float(n.mean()),
            "share_cells_2plus": float((n >= 2).mean())}


def main():
    import pandas as pd

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    args = a.parse_args()
    im.check_inputs(args.art)
    meta = json.loads((args.art / "grid.json").read_text(encoding="utf-8"))
    name = dict(enumerate(meta["names"]))
    X, names, counts, muni = im.static_matrix(args.art)
    inside = muni >= 0
    feat = {f: X[:, names.index(f)].astype(float) for f in ("pop_500", "bldg_500")}
    rows = pd.read_parquet(args.work / "labels/reports.parquet")
    rows = rows[rows.in_season & (rows.cell >= 0)]
    season = np.load(args.work / "labels/season_counts.npz")
    r040 = json.load(open(GRID / "apr_sep_report_composition.json", encoding="utf-8"))
    r039 = json.load(open(GRID / "apr_sep_positive_feature_shift.json", encoding="utf-8"))
    res = {"derived": "counts of observed reports; descriptive", "years": {}, "pairs": {},
           "reused": {"R040": "akita-bear-risk-grid-100m/outputs/apr_sep_report_composition.json",
                      "R039": "akita-bear-risk-grid-100m/outputs/apr_sep_positive_feature_shift.json"}}
    pos, hq = {}, {}
    for y in YEARS:
        r = rows[rows.bear_year == y]
        pos[y] = season[f"s{y}"][inside] > 0
        z = np.load(args.work / "scores" / YEAR_AXIS[y][0])
        hq[y] = ph.quintile(ph.percentile(z["M_H"].astype(float)))
        muni_rep = shares([name[m] for m in r.muni])
        muni_pos = shares([name[m] for m in muni[inside][pos[y]]])
        info = shares(r.info_type)
        q_of_report = hq[y][r.cell.to_numpy()]
        by_q = {}
        for q in range(1, 6):
            rq = r[q_of_report == q]
            by_q[str(q)] = {"reports": int(len(rq)), **({} if len(rq) == 0 else per_cell(rq.cell.to_numpy())),
                            "info_type_share": as_share(shares(rq.info_type)) if len(rq) else {}}
        res["years"][str(y)] = {
            "reports": int(len(r)), **per_cell(r.cell.to_numpy()),
            "municipality_report_share": as_share(muni_rep), "municipality_positive_share": as_share(muni_pos),
            "akita_city_report_share": as_share(muni_rep).get("秋田市", 0.0),
            "info_type_share": as_share(info), "info_type_count": info,
            "pop_500_positive": ph.summary(feat["pop_500"][pos[y]]), "bldg_500_positive": ph.summary(feat["bldg_500"][pos[y]]),
            "by_human_side_quintile": by_q, "human_axis": YEAR_AXIS[y][0]}
        if str(y) in r040["years"]:  # reuse check
            old = r040["years"][str(y)]
            if old["n_reports"] != len(r) or old["n_positive_cells"] != int(pos[y].sum()):
                raise ValueError(f"{y}: totals differ from R040")
            for m in old["municipalities"]:
                if abs(m["report_share"] - as_share(muni_rep).get(m["name"], 0.0)) > TOL:
                    raise ValueError(f"{y} {m['name']}: municipality share differs from R040")
            for k, v in old["info_types"].items():
                if v["count"] != info.get(k, 0):
                    raise ValueError(f"{y} {k}: info_type count differs from R040")
    for ea, eb in PAIRS:
        a_, b_ = res["years"][str(ea)], res["years"][str(eb)]
        row = {"jsd_municipality_reports": jsd_dict(a_["municipality_report_share"], b_["municipality_report_share"]),
               "jsd_info_type": jsd_dict(a_["info_type_count"], b_["info_type_count"])}
        for f in ("pop_500", "bldg_500"):
            row[f"cliff_{f}"] = ph.cliffs_delta(feat[f][pos[eb]], feat[f][pos[ea]])
            key = f"{ea}_to_{eb}"
            if key in r039["comparisons"]:
                old = r039["comparisons"][key]["features"][f]["cliffs_delta_later_minus_earlier"]
                if abs(old - row[f"cliff_{f}"]) > 1e-9:
                    raise ValueError(f"{key} {f}: Cliff's delta differs from R039")
                row[f"cliff_{f}_matches_R039"] = True
        res["pairs"][f"{ea}_to_{eb}"] = row
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for y, v in res["years"].items():
        print(y, v["reports"], v["positive_cells"], round(v["reports_per_cell"], 3), round(v["share_cells_2plus"], 3),
              "akita", round(v["akita_city_report_share"], 3), {k: round(s, 3) for k, s in v["info_type_share"].items()})
        print("   by H quintile reports/cell", {q: round(d.get("reports_per_cell", 0), 3) for q, d in v["by_human_side_quintile"].items()},
              "sighting share", {q: round(d["info_type_share"].get("目撃", 0), 3) for q, d in v["by_human_side_quintile"].items()})
    print(json.dumps(res["pairs"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

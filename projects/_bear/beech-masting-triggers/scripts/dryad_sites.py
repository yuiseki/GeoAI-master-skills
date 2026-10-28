"""The Dryad site ranks (fagus-crenata-masting-jp-2026-06) by prefecture, and the prefecture index rebuilt from them
with the forest office's weights (rank 3 全体 = 5, 2 部分 = 3, 1 一部 = 1, 0 = 0), to check that the two records are
the same survey: the rebuilt index should follow the printed 結実時 index for 1989-2008.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with numpy python projects/_bear/beech-masting-triggers/scripts/dryad_sites.py \
      projects/_bear/beech-masting-triggers/outputs
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

REV = "db40a09e24cbc02d6f19a7180bafe5f04962f8f8"
ROOT = f"hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@{REV}/parquet/"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
WEIGHT = {0: 0, 1: 1, 2: 3, 3: 5}


def rebuilt_index(ranks):
    """Mean of the weights over the sites with a rank 0-3 (NULL and -1 are left out); None if no site."""
    v = [WEIGHT[r] for r in ranks if r in WEIGHT]
    return sum(v) / len(v) if v else None


def main():
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs; install spatial; load spatial")
    sites = con.sql(f"""select s.ID, s."Site name in Japanese" name, s.Latitude lat, s.Longitude lon, s.Altitude alt,
                               a.pref, a.city
                        from '{ROOT}study_sites.parquet' s
                        left join (select pref, city, geometry::GEOMETRY g from '{ADMIN}' where ward is null) a
                          on ST_Contains(a.g, ST_Point(s.Longitude, s.Latitude)) order by s.ID""").fetchall()
    if len(sites) != 102 or len({r[0] for r in sites}) != 102 or any(r[5] is None for r in sites):
        raise ValueError("each of the 102 sites must fall in exactly one municipality")
    ranks = con.sql(f"""unpivot (select ID, columns('Obs.seed.rnk.*') from '{ROOT}seed_rank_and_cues.parquet')
                        on columns('Obs.*') into name y value v""").fetchall()  # NULLs drop out here
    by = {}
    pref_of = {r[0]: r[5] for r in sites}
    for sid, y, v in ranks:
        by.setdefault((int(y[-4:]), pref_of[sid]), []).append(int(v))
    printed = {}
    with open(a.out / "tohoku_beech_index.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["stage"] == "fruiting":
                printed[(int(r["year"]), r["pref"])] = float(r["index"])
    rows = []
    for (y, pref), rs in sorted(by.items()):
        if pref == "北海道":
            continue
        rows.append({"year": y, "pref": pref, "n_sites": sum(1 for r in rs if r in WEIGHT),
                     "n_minus_one": rs.count(-1), "rebuilt": rebuilt_index(rs), "printed": printed.get((y, pref))})
    both = [r for r in rows if r["rebuilt"] is not None and r["printed"] is not None]
    x = np.array([r["rebuilt"] for r in both])
    p = np.array([r["printed"] for r in both])
    per_pref = {}
    for pref in sorted({r["pref"] for r in both}):
        q = [r for r in both if r["pref"] == pref]
        d = np.array([r["rebuilt"] - r["printed"] for r in q])
        per_pref[pref] = {"n_years": len(q), "sites": max(r["n_sites"] for r in q),
                          "r": float(np.corrcoef([r["rebuilt"] for r in q], [r["printed"] for r in q])[0, 1]),
                          "mean_abs_diff": float(np.abs(d).mean()), "max_abs_diff": float(np.abs(d).max())}
    with open(a.out / "dryad_sites.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ID", "name", "lat", "lon", "alt", "pref", "city"])
        w.writerows(sites)
    with open(a.out / "dryad_vs_printed_index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    summary = {"pairs": len(both), "r": float(np.corrcoef(x, p)[0, 1]), "mean_abs_diff": float(np.abs(x - p).mean()),
               "share_within_0.15": float(np.mean(np.abs(x - p) <= 0.15)), "per_pref": per_pref,
               "sites_per_pref": {k: sum(1 for s in sites if s[5] == k) for k in sorted({s[5] for s in sites})},
               "dryad_revision": REV}
    (a.out / "dryad_vs_printed_index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

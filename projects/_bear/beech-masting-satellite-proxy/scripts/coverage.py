"""B0 coverage audit of the frozen Landsat 5 table (EXPERIMENT_PLAN.md). Reads no outcome.

Per site x target year t x season (previous summer = July-August of t - 1, current spring = April-May of t), on
the acquisitions kept for their site and date: the number of acquisitions, the number with at least q valid
pixels for a few q, valid pixel counts, the reasons pixels were excluded, and, for each candidate rule
(minimum valid pixels per acquisition x minimum acquisitions per season x tiers), the share of Tohoku site x t
rows with all four seasonal values and the years available for the site climatologies.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy python \
      projects/_bear/beech-masting-satellite-proxy/scripts/coverage.py REVISION projects/_bear/beech-masting-satellite-proxy/outputs
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = "yuiseki/landsat5-fagus-crenata-sites-jp-2026-10"
TARGETS = range(1990, 2009)
MIN_VALID = [1, 32, 79, 157]  # pixels: any, 10 %, 25 %, 50 % of the ~314 in the 300 m disk
MIN_SCENES = [1, 2]
TIERS = {"T1": ["T1"], "T1+T2": ["T1", "T2"]}


def load(revision):
    import duckdb

    con = duckdb.connect()
    con.sql("install httpfs; load httpfs")
    base = f"hf://datasets/{REPO}@{revision}/data/"
    acq = con.sql(f"select * from '{base}site_acquisitions.parquet'").df()
    sites = con.sql(f"select * from '{base}sites.parquet'").df()
    return acq, sites


def season_rows(acq):
    """Acquisitions keyed by target year: summer of y serves t = y + 1, spring of y serves t = y."""
    a = acq[acq.kept_for_site_date].copy()
    a["t"] = np.where(a.season == "summer", a.year + 1, a.year)
    a["window"] = np.where(a.season == "summer", "prev_summer", "current_spring")
    return a[a.t.isin(TARGETS)]


def counts(a, sites, tiers, q):
    """site x t x window: number of acquisitions with at least q valid pixels in the tiers."""
    use = a[a.tier.isin(tiers) & (a.n_valid >= q)]
    full = pd.MultiIndex.from_product([sites.ID, TARGETS, ["prev_summer", "current_spring"]], names=["ID", "t", "window"])
    return use.groupby(["ID", "t", "window"]).size().reindex(full, fill_value=0)


def rule_table(a, sites, min_years=(5, 8)):
    out = []
    for tn, tiers in TIERS.items():
        for q in MIN_VALID:
            c = counts(a, sites, tiers, q)
            for k in MIN_SCENES:
                ok = (c >= k).unstack("window")
                both = ok.all(axis=1)
                yrs = ok.groupby("ID").sum()
                row = {"tiers": tn, "min_valid": q, "min_scenes": k,
                       "share_prev_summer": float(ok.prev_summer.mean()),
                       "share_current_spring": float(ok.current_spring.mean()),
                       "share_rows_all_four": float(both.mean()), "rows_all_four": int(both.sum()),
                       "rows_all_four_dev": int(both[both.index.get_level_values("t") <= 1999].sum()),
                       "rows_all_four_confirm": int(both[both.index.get_level_values("t") >= 2000].sum())}
                for m in min_years:
                    row[f"sites_with_{m}_years_both_windows"] = int(((yrs >= m).all(axis=1)).sum())
                row["years_per_site_window_median"] = {w: float(yrs[w].median()) for w in yrs.columns}
                out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("revision")
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    acq, sites = load(a.revision)
    toh = sites[sites.region == "Tohoku region in Honshu"]
    hok = sites[sites.region != "Tohoku region in Honshu"]
    s = season_rows(acq)
    st = s[s.ID.isin(toh.ID)]
    excl = ["n_fill", "n_cloud", "n_shadow", "n_snow", "n_saturated", "n_out_of_range", "n_water"]
    res = {"revision": a.revision,
           "acquisitions": {"all_rows": len(acq), "kept_for_site_date": int(acq.kept_for_site_date.sum()),
                            "tohoku_kept_in_windows": len(st),
                            "by_tier_window": st.groupby(["tier", "window"]).size().unstack().to_dict()},
           "n_pixels": acq.n_pixels.describe().round(2).to_dict(),
           "valid_share_by_window": {w: g.assign(f=g.n_valid / g.n_pixels).f.describe(
               percentiles=[.1, .25, .5, .75, .9]).round(3).to_dict() for w, g in st.groupby("window")},
           "zero_valid_share_by_window": {w: float((g.n_valid == 0).mean()) for w, g in st.groupby("window")},
           "excluded_pixel_share_by_window": {w: {k: float(g[k].sum() / g.n_pixels.sum()) for k in excl}
                                              for w, g in st.groupby("window")},
           "rules_tohoku": rule_table(st, toh),
           "rules_hokkaido": rule_table(s[s.ID.isin(hok.ID)], hok)}
    c = counts(st, toh, ["T1"], 79).unstack("window")
    res["by_year_T1_q79_share_with_1"] = {int(t): {w: float((g[w] >= 1).mean()) for w in g.columns}
                                          for t, g in c.groupby("t")}
    per_site = (c >= 1).groupby("ID").mean()
    res["by_site_T1_q79_share_with_1"] = per_site.describe().round(3).to_dict()
    a.outputs.mkdir(parents=True, exist_ok=True)
    c.reset_index().to_csv(a.outputs / "coverage_site_year_T1_q79.csv", index=False)
    (a.outputs / "coverage_audit.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("rules_hokkaido",)}, indent=1, default=str))


if __name__ == "__main__":
    main()

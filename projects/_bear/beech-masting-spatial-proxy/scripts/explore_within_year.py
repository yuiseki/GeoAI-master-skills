"""E1 (exploratory, after B2): does the confirmed improvement over M1 carry anything spatial?

1. Within-year skill: for each confirmation year, the Spearman correlation across sites between prediction and
   observed rank (from ART/confirm_predictions.parquet, mean prediction over repeats), for M1, M2, G*, M1y.
2. Spatially flat weather: the climate columns of every row replaced by that target year's mean over the 98 sites,
   then C and B rerun for M1, M2 and G* with the frozen specification. If the RMSE does not change, the weather
   helps only as a year signal shared by all sites.
3. How much of the weather's variation is between years and how much between sites within a year.

Written after the confirmation results were seen; not a test of any claim.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python \
      projects/_bear/beech-masting-spatial-proxy/scripts/explore_within_year.py projects/_bear/beech-masting-spatial-proxy/outputs \
      artifacts/_bear/beech-masting-spatial-proxy
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import model as M
import rows as R

CONF = list(range(2000, 2009))
ALL = list(range(1990, 2009))


def within_year(pred, models):
    """{model: {"by_year": {t: rho}, "mean": mean rho}} on rows every model has, mean prediction over repeats."""
    err = M.common_rows(M.row_errors(pred), models)
    out = {}
    for m in models:
        e = err[err.model == m]
        by = {int(t): float(g.pred.rank().corr(g.y.rank())) for t, g in e.groupby("t") if g.y.nunique() > 1}
        out[m] = {"by_year": by, "mean": float(np.nanmean(list(by.values())))}
    return out


def flatten(rows):
    """Climate columns replaced by the target year's mean over the sites in `rows`."""
    r = rows.copy()
    r[R.CLIMATE_COLS] = r.groupby("t")[R.CLIMATE_COLS].transform("mean")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    choice = json.loads((a.outputs / "b1_frozen_choice.json").read_text())
    r, w, g = choice["radius"], choice["water"], choice["g_star"]
    pred = pd.read_parquet(a.art / "confirm_predictions.parquet")
    res = {"within_year_spearman": {s: within_year(pred[pred.scheme == s].drop(columns="scheme"),
                                                   ["M1", "M2", g] + (["M1y"] if s == "B" else []))
                                    for s in ("B", "C")}}
    ranks, climate, terrain, sites = R.load(a.outputs)
    rows = R.build(ranks, climate, terrain, sites, r)
    clim = R.climate_by_t(climate)
    flat = flatten(clim)
    rows_flat = rows.drop(columns=R.CLIMATE_COLS).merge(flat[["ID", "t"] + R.CLIMATE_COLS], on=["ID", "t"])
    res["flat_weather"] = {}
    for s in ("B", "C"):
        both = []
        for name, rr in (("site", rows), ("flat", rows_flat)):
            p = M.run_BC(rr, ranks, sites, s, CONF, ALL, ["M1", "M2", g], w)
            both.append(p.assign(model=lambda d, n=name: d.model + "_" + n))
        p = pd.concat(both)
        models = [f"{m}_{n}" for m in ("M1", "M2", g) for n in ("site", "flat")]
        err = M.common_rows(M.row_errors(p), models)
        sc = M.scores(err)
        res["flat_weather"][s] = {"rmse": {m: v["rmse"] for m, v in sc.items()},
                                  "M2_site_minus_flat": M.year_bootstrap(err, "M2_site", "M2_flat"),
                                  f"{g}_site_minus_flat": M.year_bootstrap(err, f"{g}_site", f"{g}_flat"),
                                  "within_year_spearman": {k: v["mean"] for k, v in within_year(p, models).items()}}
    c = clim[clim.t.isin(ALL)]
    res["variance_split"] = {}
    for col in ("dT", "WB", "Tsp"):
        between = c.groupby("t")[col].mean().var()
        within = c.groupby("t")[col].var().mean()
        res["variance_split"][col] = {"between_years": float(between), "within_year_between_sites": float(within),
                                      "share_between_years": float(between / (between + within))}
    (a.outputs / "e1_within_year.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"within_mean": {s: {m: round(v["mean"], 3) for m, v in res["within_year_spearman"][s].items()}
                                      for s in ("B", "C")},
                      "flat": {s: {k: (round(v["diff"], 4), round(v["lo90"], 4), round(v["hi90"], 4))
                                   for k, v in res["flat_weather"][s].items() if k.endswith("flat")}
                               for s in ("B", "C")},
                      "flat_within": {s: res["flat_weather"][s]["within_year_spearman"] for s in ("B", "C")},
                      "variance_split": res["variance_split"]}, indent=1))


if __name__ == "__main__":
    main()

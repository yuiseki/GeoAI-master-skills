"""Site x year weather and water cues of EXPERIMENT_PLAN.md, from the AgERA5 cell holding each of the 98 Tohoku Dryad
sites (the nearest 0.1 degree grid centre, checked to be within 0.05 degree of the site):

    Ts(y)   mean of the July and August monthly mean daily maximum temperature of year y
    Tsp(y)  mean of the April and May monthly mean daily minimum temperature of year y
    P(y)    June-August precipitation sum of year y (mm)
    PET(y)  June-August reference evapotranspiration sum of year y (mm)

each as an anomaly from the site's own 1981-2010 mean (columns without suffix), with the raw values kept (_raw_).
A missing month in a needed season stops the run. Also writes a check of Ts against Dryad's T.HSM (the summer heat
cue of the same sites; it is not the target).

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyarrow python \
      projects/beech-masting-spatial-proxy/scripts/climate.py projects/beech-masting-spatial-proxy/outputs \
      artifacts/beech-masting-spatial-proxy
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DRYAD = "hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/"
TEMP = ("hf://datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026@348e4599bffe05bc48a7033021b7e212b0f00aad"
        "/data/year={y}/part-0.parquet")
WATER_REV = "b3d1a83d2961580129e6f0222868585dc008c229"
WATER = f"hf://datasets/yuiseki/agera5-japan-monthly-water-1979-2026@{WATER_REV}/data/year={{y}}/part-0.parquet"
YEARS = range(1979, 2011)  # 1981-2010 is the base period; the cues need 1987-2008
BASE = (1981, 2010)
SEASONS = {"Ts": ("tmax_c", (7, 8), "mean"), "Tsp": ("tmin_c", (4, 5), "mean"),
           "P": ("precip_mm", (6, 7, 8), "sum"), "PET": ("et0_mm", (6, 7, 8), "sum")}


def site_year(monthly):
    """monthly: ID, year, month and the four columns. Returns ID, year, the anomalies and the raw season values."""
    out = None
    for name, (col, months, how) in SEASONS.items():
        m = monthly[monthly.month.isin(months)]
        if m[col].isna().any():
            raise ValueError(f"{name}: missing values in {col}")
        g = m.groupby(["ID", "year"])[col].agg([how, "count"]).reset_index()
        if (g["count"] != len(months)).any() or len(g) != monthly[["ID", "year"]].drop_duplicates().shape[0]:
            raise ValueError(f"{name}: a site-year without all of the months {months}")
        unit = "_raw_c" if col.endswith("_c") else "_raw_mm"
        g = g.rename(columns={how: name + unit}).drop(columns="count")
        base = g[g.year.between(*BASE)].groupby("ID")[name + unit].agg(["mean", "count"])
        if (base["count"] != BASE[1] - BASE[0] + 1).any():
            raise ValueError(f"{name}: the base period is incomplete")
        g[name] = g[name + unit] - g.ID.map(base["mean"])
        out = g if out is None else out.merge(g, on=["ID", "year"])
    return out.sort_values(["ID", "year"]).reset_index(drop=True)


def main():
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    if WATER_REV == "TO_BE_FROZEN":
        raise SystemExit("set WATER_REV to the frozen Hugging Face revision first")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    sites = con.execute(f"""SELECT ID, Latitude lat, Longitude lon FROM '{DRYAD}study_sites.parquet'
                            WHERE Location = 'Tohoku region in Honshu' ORDER BY ID""").df()
    if len(sites) != 98:
        raise ValueError("expected 98 Tohoku sites")
    con.register("sites", sites)
    con.execute(f"""CREATE TABLE cells AS
                    SELECT DISTINCT source_grid_row r, source_grid_col c,
                           ST_X(ST_GeomFromWKB(ST_AsWKB(geometry))) x, ST_Y(ST_GeomFromWKB(ST_AsWKB(geometry))) y
                    FROM read_parquet('{TEMP.format(y=2000)}')
                    WHERE month = DATE '2000-07-01' AND ST_X(ST_GeomFromWKB(ST_AsWKB(geometry))) BETWEEN 139 AND 142.5
                      AND ST_Y(ST_GeomFromWKB(ST_AsWKB(geometry))) BETWEEN 36.5 AND 41.8""")
    near = con.execute("""SELECT s.ID, c.r, c.c, c.x, c.y, greatest(abs(c.x - s.lon), abs(c.y - s.lat)) d
                          FROM sites s, cells c
                          QUALIFY row_number() OVER (PARTITION BY s.ID ORDER BY (c.x - s.lon)^2 + (c.y - s.lat)^2) = 1
                          ORDER BY s.ID""").df()
    if len(near) != 98 or (near.d > 0.0501).any():
        raise ValueError(f"a site is not inside its nearest cell: {near[near.d > 0.0501]}")
    con.register("near", near[["ID", "r", "c"]])
    tf = ", ".join(f"'{TEMP.format(y=y)}'" for y in YEARS)
    wf = ", ".join(f"'{WATER.format(y=y)}'" for y in YEARS)
    m = con.execute(f"""
        WITH t AS (SELECT month, source_grid_row r, source_grid_col c, tmax_mean_k, tmin_mean_k FROM read_parquet([{tf}])),
             w AS (SELECT month, source_grid_row r, source_grid_col c, precip_mm, et0_mm FROM read_parquet([{wf}]))
        SELECT n.ID, year(t.month) AS year, month(t.month) AS month,
               t.tmax_mean_k - 273.15 AS tmax_c, t.tmin_mean_k - 273.15 AS tmin_c, w.precip_mm, w.et0_mm
        FROM near n JOIN t ON t.r = n.r AND t.c = n.c
        LEFT JOIN w ON w.r = n.r AND w.c = n.c AND w.month = t.month
        ORDER BY 1, 2, 3""").df()
    a.art.mkdir(parents=True, exist_ok=True)
    m.to_parquet(a.art / "agera5_sites_monthly.parquet", index=False)
    per_site = m.groupby("ID").size()
    nulls = {c: int(m[c].isna().sum()) for c in ["tmax_c", "tmin_c", "precip_mm", "et0_mm"]}
    sy = site_year(m)
    sy.to_csv(a.outputs / "site_year_climate.csv", index=False, float_format="%.4f")
    near.to_csv(a.outputs / "agera5_site_cells.csv", index=False)
    # Ts against Dryad's T.HSM.YYYY (standardised summer heat cue). Which summer YYYY names is not stated, so both
    # the same year and the year before are shown.
    h = con.execute(f"""unpivot (SELECT ID, columns('T.HSM.*') FROM '{DRYAD}seed_rank_and_cues.parquet' WHERE ID >= 5)
                        on columns('T.HSM.*') into name k value hsm""").df()
    h["year"] = h.k.str[-4:].astype(int)
    check = {}
    for lag in (0, 1):
        j = h.assign(year=h.year - lag).merge(sy[["ID", "year", "Ts"]], on=["ID", "year"]).dropna()
        check[f"Ts(YYYY-{lag})"] = {"n": len(j), "pearson": float(np.corrcoef(j.hsm, j.Ts)[0, 1]),
                                    "spearman": float(j.hsm.rank().corr(j.Ts.rank()))}
    audit = {"sites": len(near), "distinct_cells": int(near[["r", "c"]].drop_duplicates().shape[0]),
             "max_site_cell_offset_deg": float(near.d.max()), "months_per_site": [int(per_site.min()), int(per_site.max())],
             "nulls": nulls, "site_years": len(sy), "years": [int(sy.year.min()), int(sy.year.max())],
             "temperature_revision": TEMP.split("@")[1].split("/")[0], "water_revision": WATER_REV,
             "ts_vs_dryad_thsm": check,
             "season_raw_ranges": {c: [float(sy[c].min()), float(sy[c].max())]
                                   for c in sy.columns if "_raw_" in c}}
    (a.outputs / "climate_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

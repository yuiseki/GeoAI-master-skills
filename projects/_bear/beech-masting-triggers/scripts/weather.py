"""AgERA5 monthly mean daily maximum and minimum temperature at the Dryad beech sites, and the weather cues of the
plan (EXPERIMENT_PLAN.md) per prefecture and year.

Each Tohoku site takes the 0.1 degree grid centre nearest to it (checked to be within the cell, 0.0708 degree).
A prefecture's value for a month is the mean over its sites (two sites in one cell give that cell twice).
Cues are anomalies (°C) from the prefecture's 1981-2010 mean of the same cue:
    Ts(y)  = mean of the July and August Tmax of year y
    Tsp(y) = mean of the April and May Tmin of year y

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas python projects/_bear/beech-masting-triggers/scripts/weather.py \
      projects/_bear/beech-masting-triggers/outputs artifacts/_bear/beech-masting-triggers
"""

import argparse
from pathlib import Path

import pandas as pd

AGERA5 = ("hf://datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026@348e4599bffe05bc48a7033021b7e212b0f00aad"
          "/data/year={y}/part-0.parquet")
YEARS = range(1979, 2027)
BASE = (1981, 2010)
CUES = {"Ts": ("tmax_c", (7, 8)), "Tsp": ("tmin_c", (4, 5))}


def cues(monthly):
    """monthly: pref, year, month, tmax_c, tmin_c. Returns pref, year, Ts, Tsp (anomalies) and the raw means.

    The last year of the data may not have reached the cue's months yet (the summer of the current year); its cue
    is left out. A gap in any earlier year stops.
    """
    out = []
    last = monthly.year.max()
    for name, (col, months) in CUES.items():
        m = monthly[monthly.month.isin(months)].groupby(["pref", "year"])[col].agg(["mean", "count"]).reset_index()
        m = m.merge(monthly[["pref", "year"]].drop_duplicates(), how="right", on=["pref", "year"]).fillna({"count": 0})
        short = m["count"] != len(months)
        if (short & (m.year != last)).any():
            raise ValueError(f"{name}: years without all of the months {months}")
        m = m[~short]
        base = m[m.year.between(*BASE)].groupby("pref")["mean"].mean().rename("base")
        if (m[m.year.between(*BASE)].groupby("pref").size() != BASE[1] - BASE[0] + 1).any():
            raise ValueError(f"{name}: the base period is incomplete")
        m = m.join(base, on="pref")
        m[name] = m["mean"] - m["base"]
        m[name + "_raw_c"] = m["mean"]
        out.append(m[["pref", "year", name, name + "_raw_c"]])
    return out[0].merge(out[1], on=["pref", "year"], how="outer").sort_values(["pref", "year"]).reset_index(drop=True)


def main():
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    sites = pd.read_csv(a.outputs / "dryad_sites.csv")
    sites = sites[sites.pref != "北海道"]
    if len(sites) != 98:
        raise ValueError("expected 98 Tohoku sites")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.register("sites", sites)
    con.execute(f"""CREATE TABLE cells AS
                    SELECT DISTINCT source_grid_row r, source_grid_col c,
                           ST_X(ST_GeomFromWKB(ST_AsWKB(geometry))) x, ST_Y(ST_GeomFromWKB(ST_AsWKB(geometry))) y
                    FROM read_parquet('{AGERA5.format(y=2000)}')
                    WHERE month = DATE '2000-07-01' AND ST_X(ST_GeomFromWKB(ST_AsWKB(geometry))) BETWEEN 139 AND 142.5
                      AND ST_Y(ST_GeomFromWKB(ST_AsWKB(geometry))) BETWEEN 36.5 AND 41.8""")
    near = con.execute("""SELECT s.ID, s.pref, c.r, c.c, c.x, c.y, s.lon, s.lat,
                                 greatest(abs(c.x - s.lon), abs(c.y - s.lat)) d
                          FROM sites s, cells c
                          QUALIFY row_number() OVER (PARTITION BY s.ID ORDER BY (c.x - s.lon)^2 + (c.y - s.lat)^2) = 1
                          ORDER BY s.ID""").df()
    if len(near) != 98 or (near.d > 0.0501).any():
        raise ValueError(f"a site is not inside its nearest cell: {near[near.d > 0.0501]}")
    con.register("near", near[["ID", "pref", "r", "c"]])
    files = ", ".join(f"'{AGERA5.format(y=y)}'" for y in YEARS)
    m = con.execute(f"""SELECT n.ID, n.pref, year(t.month) AS year, month(t.month) AS month,
                               t.tmax_mean_k - 273.15 AS tmax_c, t.tmin_mean_k - 273.15 AS tmin_c
                        FROM read_parquet([{files}]) t JOIN near n ON t.source_grid_row = n.r AND t.source_grid_col = n.c
                        ORDER BY 1, 3, 4""").df()
    per_site = m.groupby("ID").size()
    a.art.mkdir(parents=True, exist_ok=True)
    m.to_parquet(a.art / "agera5_sites_monthly.parquet", index=False)
    nulls = int(m.tmax_c.isna().sum() + m.tmin_c.isna().sum())
    monthly = m.groupby(["pref", "year", "month"])[["tmax_c", "tmin_c"]].mean().reset_index()
    c = cues(monthly)
    c.to_csv(a.outputs / "cues_weather.csv", index=False, float_format="%.4f")
    near.to_csv(a.outputs / "agera5_site_cells.csv", index=False)
    print("sites", len(near), "distinct cells", near[["r", "c"]].drop_duplicates().shape[0],
          "months per site", per_site.min(), per_site.max(), "nulls", nulls,
          "last month", m.year.max(), m[m.year == m.year.max()].month.max(), "cue rows", len(c), flush=True)


if __name__ == "__main__":
    main()

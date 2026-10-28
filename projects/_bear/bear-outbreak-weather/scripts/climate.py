"""Monthly mean daily maximum temperature (AgERA5 v2.0, 0.1 degree) averaged over the grid centres inside each
prefecture, for 2005-2025, and the summer (June to August) mean per year.

Writes OUT_DIR/tmax_monthly.csv (region, year, month, tmax_c, points) and OUT_DIR/summer_tmax.csv (region, year,
summer_tmax_c). A month with a missing value at some points is averaged over the points that have one; the count
of points is kept.

Usage:
    uvx --from 'duckdb>=1.5.5' --with pandas python climate.py OUT_DIR
"""

import sys

import pandas as pd

AGERA5 = "hf://datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026@348e4599bffe05bc48a7033021b7e212b0f00aad/data/year={y}/part-0.parquet"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
PREFS = {"akita": "05", "gifu": "21", "kyoto": "26", "ishikawa": "17"}
YEARS = range(2005, 2026)


def summer(monthly):
    s = monthly[monthly.month.between(6, 8)].groupby(["region", "year"]).agg(summer_tmax_c=("tmax_c", "mean"), months=("month", "size")).reset_index()
    if (s.months != 3).any():
        raise ValueError(f"summers without all three months: {s[s.months != 3]}")
    return s.drop(columns="months")


def main():
    import duckdb

    out = sys.argv[1]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute(f"""CREATE TABLE pref AS SELECT pref_code, ST_Union_Agg(ST_GeomFromWKB(ST_AsWKB(geometry))) g
                    FROM read_parquet('{ADMIN}') WHERE pref_code IN ({','.join(f"'{c}'" for c in PREFS.values())})
                      AND ward IS NULL AND geometry IS NOT NULL GROUP BY 1""")
    files = ", ".join(f"'{AGERA5.format(y=y)}'" for y in YEARS)
    con.execute(f"""CREATE TABLE pts AS SELECT DISTINCT source_grid_row r, source_grid_col c, ST_GeomFromWKB(ST_AsWKB(geometry)) p
                    FROM read_parquet('{AGERA5.format(y=2020)}') WHERE month = DATE '2020-07-01'""")
    con.execute("CREATE TABLE inpref AS SELECT pts.r, pts.c, pref.pref_code FROM pts JOIN pref ON ST_Within(pts.p, pref.g)")
    print("grid centres per prefecture:", con.execute("SELECT pref_code, count(*) FROM inpref GROUP BY 1 ORDER BY 1").fetchall())
    m = con.execute(f"""SELECT i.pref_code, year(t.month) AS year, month(t.month) AS month,
                               avg(t.tmax_mean_k) - 273.15 AS tmax_c, count(t.tmax_mean_k) AS points, count(*) AS rows
                        FROM read_parquet([{files}]) t JOIN inpref i ON t.source_grid_row = i.r AND t.source_grid_col = i.c
                        GROUP BY ALL ORDER BY 1, 2, 3""").df()
    m["region"] = m.pref_code.map({v: k for k, v in PREFS.items()})
    print("months with missing points:", int((m.points < m.rows).sum()), "of", len(m))
    m[["region", "year", "month", "tmax_c", "points"]].to_csv(f"{out}/tmax_monthly.csv", index=False)
    s = summer(m)
    s.to_csv(f"{out}/summer_tmax.csv", index=False)
    print(s.pivot(index="year", columns="region", values="summer_tmax_c").round(2).to_string())


if __name__ == "__main__":
    main()

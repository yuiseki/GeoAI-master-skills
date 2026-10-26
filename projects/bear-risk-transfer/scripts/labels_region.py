"""Bear reports of one region, counted in its 100 m cells: the total over the whole period and per period (year).

    gifu       the 12 yearly tables of the Gifu Kuma map; the period is the fiscal year of the table
    kyoto      the Kyoto sighting table; the period is fiscal_year
    ishikawa   the five overlapping cause tables of R1-R6 (one report can be in several), kept once per date, place
               and point (6 decimals), and the R7 sighting table; the period is the calendar year of the date
    nagaoka    the Nagaoka sighting table; the period is fiscal_year

Every kind of report counts (sightings, traces, injuries), as for the Akita model. Points in no cell of the region
(the sea, the neighbouring prefectures) are counted and left out. Writes reports.npz: `total` and `p<period>`.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyproj python labels_region.py REGION ART_DIR
"""

import sys

import numpy as np
import pandas as pd

from grid import load

GIFU = "hf://datasets/yuiseki/gifu-bear-sighting@b7f59470885e485b53cfbdddc0b2e0c2ceb11661/parquet/"
GIFU_TABLES = [("h26", 2014), ("h27", 2015), ("h28", 2016), ("h29", 2017), ("h30", 2018), ("r1", 2019),
               ("r2", 2020), ("r3", 2021), ("r4", 2022), ("r5", 2023), ("r6", 2024), ("r7", 2025)]
KYOTO = "hf://datasets/yuiseki/kyoto-bear-sighting@a2a50c4bd863efe96ef7ed8087ee4e1d0db01858/parquet/sighting.parquet"
ISHIKAWA = "hf://datasets/yuiseki/ishikawa-bear-incident@d2b77a201a1ab2cfa0534a7c8b513a495179f24a/parquet/"
ISHIKAWA_CAUSES = ["forest_r1_r6", "river_r1_r6", "attractants_r1_r6", "young_bears_r1_r6", "mass_outbreak_r2"]
NAGAOKA = "hf://datasets/yuiseki/nagaoka-bear-sighting@724bde2a1b5168ae39e9a4a781220d28fabeb762/parquet/sighting.parquet"


def dedupe(df, keys):
    k = df.assign(_lon=df.lon.round(6), _lat=df.lat.round(6))
    return k.drop_duplicates(keys + ["_lon", "_lat"]).drop(columns=["_lon", "_lat"])


def counts(grid, lab, pts):
    """Total and per-period [ny, nx] counts of points (columns x, y, period) in the region's cells; and how many fell outside."""
    ix, iy, ok = grid.index(pts.x.to_numpy(), pts.y.to_numpy())
    inside = np.zeros(len(pts), dtype=bool)
    inside[ok] = lab[iy[ok], ix[ok]] >= 0
    p = pts[inside]
    total, _ = grid.sum_into(p.x.to_numpy(), p.y.to_numpy())
    by = {int(per): grid.sum_into(g.x.to_numpy(), g.y.to_numpy())[0] for per, g in p.groupby("period")}
    return total, by, int((~inside).sum())


def read(region, con):
    q = lambda s: con.execute(s).df()
    if region == "gifu":
        parts = [q(f"SELECT ST_X(geometry) lon, ST_Y(geometry) lat, {fy} AS period FROM '{GIFU}{t}.parquet'") for t, fy in GIFU_TABLES]
        return pd.concat(parts, ignore_index=True)
    if region == "kyoto":
        return q(f"SELECT ST_X(geometry) lon, ST_Y(geometry) lat, fiscal_year AS period FROM '{KYOTO}'")
    if region == "nagaoka":
        return q(f"SELECT ST_X(geometry) lon, ST_Y(geometry) lat, fiscal_year AS period FROM '{NAGAOKA}'")
    if region == "ishikawa":
        cause = pd.concat([q(f"SELECT date, place, ST_X(geometry) lon, ST_Y(geometry) lat FROM '{ISHIKAWA}{t}.parquet'") for t in ISHIKAWA_CAUSES], ignore_index=True)
        n0 = len(cause)
        no_date = int(cause.date.isna().sum())
        cause = dedupe(cause, ["date", "place"])
        print(f"ishikawa cause tables: {n0} rows -> {len(cause)} after keeping one per date, place and point; rows without a date {no_date}")
        r7 = q(f"SELECT date, NULL AS place, ST_X(geometry) lon, ST_Y(geometry) lat FROM '{ISHIKAWA}sightings_r7.parquet'")
        df = pd.concat([cause, r7], ignore_index=True)
        if df.date.isna().any():
            print(f"rows without a date (left out of the per-year counts, kept in the total): {int(df.date.isna().sum())}")
        df["period"] = pd.to_datetime(df.date).dt.year.fillna(0).astype(int)
        return df[["lon", "lat", "period"]]
    raise SystemExit(f"unknown region {region}")


def main():
    import duckdb
    import pyproj

    region, art = sys.argv[1], sys.argv[2]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    df = read(region, con)
    n_null = int(df[["lon", "lat"]].isna().any(axis=1).sum())
    if n_null:
        print(f"rows without a point: {n_null} (left out)")
        df = df.dropna(subset=["lon", "lat"])
    g, crs = load(art)
    lab = np.load(f"{art}/grid_mask.npz")["muni"]
    x, y = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(df.lon.to_numpy(), df.lat.to_numpy())
    pts = pd.DataFrame({"x": x, "y": y, "period": df.period.to_numpy()})
    total, by, off = counts(g, lab, pts)
    inside = lab >= 0
    print(f"{region}: reports {len(pts)} = in the region's cells {int(total.sum())} + outside {off}: {len(pts) == int(total.sum()) + off}")
    print(f"cells with >= 1 report: {int((total[inside] > 0).sum())} of {int(inside.sum())} ({(total[inside] > 0).mean():.4%})")
    print("reports per period:", {k: int(v.sum()) for k, v in sorted(by.items())})
    np.savez_compressed(f"{art}/reports.npz", total=total.astype(np.int32), **{f"p{k}": v.astype(np.int32) for k, v in by.items()})


if __name__ == "__main__":
    main()

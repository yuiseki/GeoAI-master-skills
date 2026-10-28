"""Bear reports per prefecture and year: the autumn (September to December) and the whole year (April to March,
or the calendar year for Ishikawa, whose data come in calendar years).

    akita     Kumadas, bear reports, years 2022-2025 (bear year April to March; autumn of the same year)
    gifu      Kuma map (past), FY2014-FY2025; the month from the text (`０９月`, `9`); rows without a readable month
              count in the year but not in the autumn
    kyoto     FY2009-FY2018 (2018 ends on 10 December)
    ishikawa  the five cause tables of R1-R6 kept once per date, place and point; 2019-2024 calendar years

Writes OUT.csv: region, year, autumn, whole.

Usage:
    uvx --from 'duckdb>=1.5.5' --with pandas python outcomes.py OUT.csv
"""

import re
import sys
import unicodedata

import pandas as pd

AKITA = "hf://datasets/yuiseki/akita-kumadas-wildlife-sighting@c7047ab442ea3471aaa52af6e56a966ac768ff61/parquet/sighting.parquet"
GIFU = "hf://datasets/yuiseki/gifu-bear-sighting@b7f59470885e485b53cfbdddc0b2e0c2ceb11661/parquet/"
GIFU_TABLES = [("h26", 2014), ("h27", 2015), ("h28", 2016), ("h29", 2017), ("h30", 2018), ("r1", 2019),
               ("r2", 2020), ("r3", 2021), ("r4", 2022), ("r5", 2023), ("r6", 2024), ("r7", 2025)]
KYOTO = "hf://datasets/yuiseki/kyoto-bear-sighting@a2a50c4bd863efe96ef7ed8087ee4e1d0db01858/parquet/sighting.parquet"
ISHIKAWA = "hf://datasets/yuiseki/ishikawa-bear-incident@d2b77a201a1ab2cfa0534a7c8b513a495179f24a/parquet/"
CAUSES = ["forest_r1_r6", "river_r1_r6", "attractants_r1_r6", "young_bears_r1_r6", "mass_outbreak_r2"]


def parse_month(text):
    if text is None:
        return None
    m = re.fullmatch(r"(\d{1,2})月?", unicodedata.normalize("NFKC", str(text)).strip())
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 12 else None


def dedupe(df, keys):
    k = df.assign(_lon=df.lon.round(6), _lat=df.lat.round(6))
    return k.drop_duplicates(keys + ["_lon", "_lat"]).drop(columns=["_lon", "_lat"])


def tally(df, region):
    """df: one row per report with `year` (the season's year) and `month` (may be missing)."""
    autumn = df.month.between(9, 12)
    t = df.assign(autumn=autumn.astype(int)).groupby("year").agg(autumn=("autumn", "sum"), whole=("autumn", "size")).reset_index()
    t.insert(0, "region", region)
    return t


def main():
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    q = lambda s: con.execute(s).df()
    out = []
    a = q(f"SELECT observed_at FROM '{AKITA}' WHERE species = 'ツキノワグマ'")
    m = a.observed_at.dt.month
    a = pd.DataFrame({"year": a.observed_at.dt.year.where(m >= 4, a.observed_at.dt.year - 1), "month": m})
    out.append(tally(a[a.year.between(2022, 2025)], "akita"))
    g = []
    for t, fy in GIFU_TABLES:
        d = q(f'SELECT "出没月" AS mt FROM \'{GIFU}{t}.parquet\'')
        g.append(pd.DataFrame({"year": fy, "month": [parse_month(x) for x in d.mt]}))
    g = pd.concat(g, ignore_index=True)
    print(f"gifu: {len(g)} rows, month unreadable {int(g.month.isna().sum())}")
    out.append(tally(g, "gifu"))
    k = q(f"SELECT date, fiscal_year FROM '{KYOTO}'")
    out.append(tally(pd.DataFrame({"year": k.fiscal_year, "month": pd.to_datetime(k.date).dt.month}), "kyoto"))
    c = pd.concat([q(f"SELECT date, place, ST_X(geometry) lon, ST_Y(geometry) lat FROM '{ISHIKAWA}{t}.parquet'") for t in CAUSES], ignore_index=True)
    c = dedupe(c, ["date", "place"]).dropna(subset=["date"])
    d = pd.to_datetime(c.date)
    i = pd.DataFrame({"year": d.dt.year, "month": d.dt.month})
    out.append(tally(i[i.year.between(2019, 2024)], "ishikawa"))
    res = pd.concat(out, ignore_index=True)
    res.to_csv(sys.argv[1], index=False)
    print(res.groupby("region").agg(years=("year", "size"), first=("year", "min"), last=("year", "max"), autumn=("autumn", "sum"), whole=("whole", "sum")))


if __name__ == "__main__":
    main()

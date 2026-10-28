"""Build the municipality x month table of bear reports in Gifu (Kuma map, past) and write it to Parquet.

One row per (municipality, month), zeros included, FY2014 April to FY2025 March (144 months).
Columns: code5, month_start, bear, name, population.

The 12 yearly tables share the columns `出没月` and `出没日`, as text with full-width digits
(`０４月`). The calendar year comes from the fiscal year of the file: April to December are in the
fiscal year, January to March in the next. A municipality is given by the polygon of
jp-admin-2026-09 that the point falls in (the card says to do so: the files have no municipality
code). Rows whose month cannot be read, and points in no Gifu polygon (a few lie just across the
prefecture border), are counted and printed, not dropped silently.

Usage:
    uvx --from 'duckdb>=1.5.5' python build_table_gifu.py OUT.parquet
"""

import argparse
import datetime as dt
import re
import unicodedata

import duckdb

REV = "b7f59470885e485b53cfbdddc0b2e0c2ceb11661"
GIFU = f"hf://datasets/yuiseki/gifu-bear-sighting@{REV}/parquet/"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
TABLES = [("h26", 2014), ("h27", 2015), ("h28", 2016), ("h29", 2017), ("h30", 2018), ("r1", 2019),
          ("r2", 2020), ("r3", 2021), ("r4", 2022), ("r5", 2023), ("r6", 2024), ("r7", 2025)]


def parse_month(text):
    """Month 1..12 from text such as `０４月`, `4月`, `１１月` or a bare `6`; None when it cannot be read (`１０時`, empty)."""
    if text is None:
        return None
    t = unicodedata.normalize("NFKC", str(text)).strip()
    m = re.fullmatch(r"(\d{1,2})月?", t)
    if not m:
        return None
    month = int(m.group(1))
    return month if 1 <= month <= 12 else None


def calendar_month(fy, month):
    """First day of the calendar month: January to March belong to the next calendar year of the fiscal year."""
    return dt.date(fy if month >= 4 else fy + 1, month, 1)


def monthly_table(con, first_month, last_month):
    """Rows (code5, month_start, bear) for every municipality in `munis` and every month.

    `con` has `sighting` (fy, month_start, code5) and `munis` (code5, name). The count of rows outside
    the months is left in monthly_table.last_outside.
    """
    if first_month.day != 1 or last_month.day != 1:
        raise ValueError("first_month and last_month must be the first of a month")
    monthly_table.last_outside = con.execute(
        "SELECT count(*) FROM sighting WHERE month_start < ? OR month_start > ?", [first_month, last_month]
    ).fetchone()[0]
    return con.execute(
        """
        WITH months AS (SELECT unnest(generate_series(?::DATE, ?::DATE, INTERVAL 1 MONTH))::DATE AS month_start),
        grid AS (SELECT m.code5, w.month_start FROM munis m CROSS JOIN months w),
        c AS (SELECT code5, month_start, count(*) AS bear FROM sighting GROUP BY ALL)
        SELECT g.code5, g.month_start, coalesce(c.bear, 0)::BIGINT
        FROM grid g LEFT JOIN c USING (code5, month_start)
        ORDER BY g.code5, g.month_start
        """,
        [first_month, last_month],
    ).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    a = ap.parse_args()

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute(f"""CREATE TABLE munis AS SELECT code5, name, population FROM read_parquet('{ADMIN}')
                    WHERE pref_code = '21' AND ward IS NULL AND geometry IS NOT NULL""")
    con.execute(f"""CREATE TABLE admin AS SELECT code5, ST_GeomFromWKB(ST_AsWKB(geometry)) AS g
                    FROM read_parquet('{ADMIN}') WHERE pref_code = '21' AND ward IS NULL AND geometry IS NOT NULL""")
    n_munis = con.execute("SELECT count(*) FROM munis").fetchone()[0]
    print("Gifu municipalities in jp-admin-2026-09:", n_munis)

    con.execute("CREATE TABLE s0 (tbl VARCHAR, fy INT, row INT, month_start DATE, p GEOMETRY)")
    unreadable, total = {}, 0
    for t, fy in TABLES:
        rows = con.execute(
            f'SELECT row, "出没月", ST_X(geometry), ST_Y(geometry) FROM read_parquet(\'{GIFU}{t}.parquet\')'
        ).fetchall()
        total += len(rows)
        ok = []
        for row, mtext, lon, lat in rows:
            month = parse_month(mtext)
            if month is None:
                unreadable[t] = unreadable.get(t, 0) + 1
                continue
            ok.append((t, fy, row, calendar_month(fy, month), f"POINT({lon} {lat})"))
        con.executemany("INSERT INTO s0 VALUES (?,?,?,?,ST_GeomFromText(?))", ok)
    print(f"rows read: {total}; month unreadable: {sum(unreadable.values())} {unreadable}")

    # one polygon per point: the overlap slivers between neighbours could match a point twice
    con.execute("""
        CREATE TABLE joined AS
        SELECT tbl, fy, row, month_start, code5 FROM (
            SELECT s.tbl, s.fy, s.row, s.month_start, a.code5,
                   row_number() OVER (PARTITION BY s.tbl, s.row ORDER BY a.code5) AS rk
            FROM s0 s LEFT JOIN admin a ON ST_Within(s.p, a.g)
        ) WHERE rk = 1""")
    n_in = con.execute("SELECT count(*) FROM s0").fetchone()[0]
    n_all = con.execute("SELECT count(*) FROM joined").fetchone()[0]
    print(f"parsed rows {n_in} -> {n_all} after the polygon join (must be equal)")
    if n_in != n_all:
        raise SystemExit("the municipality join duplicated or lost rows")
    multi = con.execute("""SELECT count(*) FROM (SELECT s.tbl, s.row FROM s0 s JOIN admin a ON ST_Within(s.p, a.g)
                           GROUP BY ALL HAVING count(*) > 1)""").fetchone()[0]
    print("points in more than one Gifu polygon (the lowest code was taken):", multi)
    out_rows = con.execute("SELECT tbl, count(*) FROM joined WHERE code5 IS NULL GROUP BY ALL ORDER BY 1").fetchall()
    n_outside_gifu = sum(r[1] for r in out_rows)
    print("points in no Gifu polygon, by table:", out_rows, "total", n_outside_gifu)
    con.execute("CREATE TABLE sighting AS SELECT fy, month_start, code5 FROM joined WHERE code5 IS NOT NULL")

    first, last = dt.date(2014, 4, 1), dt.date(2026, 3, 1)
    rows = monthly_table(con, first, last)
    inside = sum(r[2] for r in rows)
    print(f"months {first}..{last}: {len(rows)} rows = {n_munis} x {len(rows) // n_munis}; reports inside {inside}, outside the months {monthly_table.last_outside}")
    print(f"conservation: read {total} = {inside} counted + {sum(unreadable.values())} unreadable + {n_outside_gifu} outside Gifu + {monthly_table.last_outside} outside months:",
          total == inside + sum(unreadable.values()) + n_outside_gifu + monthly_table.last_outside)
    print("per fiscal year:", con.execute("SELECT fy, count(*) FROM sighting GROUP BY ALL ORDER BY 1").fetchall())

    con.execute("CREATE TABLE out (code5 VARCHAR, month_start DATE, bear BIGINT)")
    con.executemany("INSERT INTO out VALUES (?,?,?)", rows)
    con.execute(f"COPY (SELECT o.*, m.name, m.population FROM out o JOIN munis m USING (code5) ORDER BY code5, month_start) TO '{a.out}' (FORMAT PARQUET)")
    print("wrote", a.out)


if __name__ == "__main__":
    main()

"""Build the municipality x week table of bear reports in Akita (Kumadas) and write it to Parquet.

One row per (municipality, Monday-start week), zeros included. Columns:
    code5       5-digit municipality code (from the point in jp-admin-2026-09; recorded name only if the point is in no polygon)
    week_start  Monday of the week (JST, the data carry no time zone)
    bear        reports of Asiatic black bear of every kind (sighting, traces, damage to crops, injury)
    bear_sight  of those, sightings only
    injury      of those, injuries to people

Weeks run from first_week to last_week, both complete. Rows outside them are counted and printed,
not dropped silently. A point is given a municipality by the polygon it falls in; the
recorded name is used only where the point falls in no polygon (the sea, a lake), and those
rows are counted and printed.

Usage:
    uvx --from 'duckdb>=1.5.5' python build_table.py OUT.parquet [--first 2022-04-11 --last 2026-09-21] [--sighting PARQUET_OR_URL]
"""

import argparse
import datetime as dt

import duckdb

SIGHTING = "hf://datasets/yuiseki/akita-kumadas-wildlife-sighting@c7047ab442ea3471aaa52af6e56a966ac768ff61/parquet/sighting.parquet"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"


def weekly_table(con, first_week, last_week):
    """Rows (code5, week_start, bear, bear_sight, injury) for every municipality in `munis` and every week.

    `con` has `sighting` (species, info_type, observed_at, code5) and `munis` (code5, name).
    The count of bear rows that fall outside the weeks is left in weekly_table.last_outside.
    """
    if first_week.weekday() != 0 or last_week.weekday() != 0:
        raise ValueError("first_week and last_week must be Mondays")
    n_null = con.execute("SELECT count(*) FROM sighting WHERE species = 'ツキノワグマ' AND code5 IS NULL").fetchone()[0]
    if n_null:
        raise ValueError(f"{n_null} bear rows have no municipality code")
    weekly_table.last_outside = con.execute(
        "SELECT count(*) FROM sighting WHERE species = 'ツキノワグマ' AND (date_trunc('week', observed_at)::DATE < ? OR date_trunc('week', observed_at)::DATE > ?)",
        [first_week, last_week],
    ).fetchone()[0]
    return con.execute(
        """
        WITH weeks AS (SELECT unnest(generate_series(?::DATE, ?::DATE, INTERVAL 7 DAY))::DATE AS week_start),
        grid AS (SELECT m.code5, w.week_start FROM munis m CROSS JOIN weeks w),
        c AS (
            SELECT code5, date_trunc('week', observed_at)::DATE AS week_start,
                   count(*) AS bear,
                   count(*) FILTER (info_type = '目撃') AS bear_sight,
                   count(*) FILTER (info_type = '人身被害') AS injury
            FROM sighting WHERE species = 'ツキノワグマ' GROUP BY ALL
        )
        SELECT g.code5, g.week_start, coalesce(c.bear, 0)::BIGINT, coalesce(c.bear_sight, 0)::BIGINT, coalesce(c.injury, 0)::BIGINT
        FROM grid g LEFT JOIN c USING (code5, week_start)
        ORDER BY g.code5, g.week_start
        """,
        [first_week, last_week],
    ).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--first", default="2022-04-11")
    ap.add_argument("--last", default="2026-09-21")
    ap.add_argument("--sighting", default=SIGHTING, help="Parquet of a later version of the sightings (the default is the pinned 2026-09-30 version)")
    a = ap.parse_args()
    first, last = dt.date.fromisoformat(a.first), dt.date.fromisoformat(a.last)

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE admin AS SELECT code5, name, population, ST_GeomFromWKB(ST_AsWKB(geometry)) AS g FROM read_parquet('{ADMIN}') WHERE pref_code = '05' AND ward IS NULL AND geometry IS NOT NULL")
    n_munis = con.execute("SELECT count(*) FROM admin").fetchone()[0]
    print("Akita municipalities in jp-admin-2026-09:", n_munis)
    con.execute("CREATE TABLE munis AS SELECT code5, name, population FROM admin")

    # the points are OGC:CRS84 and the polygons EPSG:4612; both are (lon, lat), so build plain points
    con.execute(f"""
        CREATE TABLE s0 AS SELECT id, species, info_type, municipality, observed_at,
               ST_Point(longitude, latitude) AS p FROM read_parquet('{a.sighting}')""")
    con.execute("""
        CREATE TABLE sighting AS
        SELECT s0.id, s0.species, s0.info_type, s0.municipality, s0.observed_at,
               coalesce(a.code5, n.code5) AS code5,
               CASE WHEN a.code5 IS NOT NULL THEN 'polygon' WHEN n.code5 IS NOT NULL THEN 'name' ELSE 'none' END AS how
        FROM s0
        LEFT JOIN admin a ON ST_Within(s0.p, a.g)
        LEFT JOIN munis n ON n.name = s0.municipality AND a.code5 IS NULL
        """)
    print("how each row got its municipality:", con.execute("SELECT how, count(*) FROM sighting GROUP BY ALL ORDER BY 2 DESC").fetchall())
    n_total = con.execute("SELECT count(*) FROM s0").fetchone()[0]
    n_after = con.execute("SELECT count(*) FROM sighting").fetchone()[0]
    print(f"rows: {n_total} -> {n_after} after the join (a polygon overlap would make this larger)")
    if n_after != n_total:
        raise SystemExit("the municipality join duplicated or lost rows")

    rows = weekly_table(con, first, last)
    print(f"weeks {first}..{last}: {len(rows)} rows = {n_munis} municipalities x {len(rows) // n_munis} weeks")
    print("bear rows outside the weeks:", weekly_table.last_outside)
    n_bear = con.execute("SELECT count(*) FROM sighting WHERE species = 'ツキノワグマ'").fetchone()[0]
    inside = sum(r[2] for r in rows)
    print(f"bear rows: {n_bear} = {inside} inside + {weekly_table.last_outside} outside:", n_bear == inside + weekly_table.last_outside)

    con.execute("CREATE TABLE out (code5 VARCHAR, week_start DATE, bear BIGINT, bear_sight BIGINT, injury BIGINT)")
    con.executemany("INSERT INTO out VALUES (?,?,?,?,?)", rows)
    con.execute("COPY (SELECT o.*, m.name, m.population FROM out o JOIN munis m USING (code5) ORDER BY code5, week_start) TO ? (FORMAT PARQUET)".replace("?", f"'{a.out}'"))
    print("wrote", a.out)


if __name__ == "__main__":
    main()

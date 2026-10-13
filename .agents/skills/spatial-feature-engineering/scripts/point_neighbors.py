"""Count reference points within given radii of each query point, and the distance to the nearest one.

Distances are great-circle kilometres on a sphere of radius 6,371 km, correct at any latitude and
across the antimeridian: points are placed on the unit sphere in 3D, bucketed into cubes as wide
as the largest radius's chord, and compared by chord length.

Output columns: <query id>, n_within_<r>km for each radius, nearest_km. nearest_km is NULL when no
reference point lies within the largest radius. With --exclude-self, a reference point whose id
equals the query point's id is not counted (use it when query and reference are the same data).

Usage:
    uvx --from 'duckdb>=1.5.5' python point_neighbors.py QUERY QUERY_ID REFERENCE REFERENCE_ID \
        --radii-km 10 50 [--exclude-self] [--query-where SQL] [--reference-where SQL] --out OUT
"""

import argparse
import math

import duckdb

EARTH_KM = 6371.0


def chord(km):
    """Straight-line distance on the unit sphere for a great-circle distance in km."""
    return 2 * math.sin(km / EARTH_KM / 2)


def neighbors(query, query_id, reference, reference_id, radii_km, exclude_self, query_where,
              reference_where, out):
    radii_km = sorted(radii_km)
    if radii_km[-1] >= math.pi * EARTH_KM / 2:
        raise SystemExit("the largest radius must be under a quarter of the earth's circumference")
    cell = chord(radii_km[-1])

    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    for name, src, pid, where in (
        ("q", query, query_id, query_where),
        ("r", reference, reference_id, reference_where),
    ):
        con.sql(f"""
            create table {name} as
            with p as (
                select "{pid}" as id, radians(ST_Y(geometry)) as lat, radians(ST_X(geometry)) as lon
                from '{src}' where {where or 'true'}
            ), xyz as (
                select id, cos(lat) * cos(lon) as x, cos(lat) * sin(lon) as y, sin(lat) as z from p
            )
            select *, floor(x / {cell})::bigint as cx, floor(y / {cell})::bigint as cy,
                   floor(z / {cell})::bigint as cz
            from xyz
        """)
    n_query = con.sql("select count(*) from q").fetchone()[0]
    if con.sql("select count(*) - count(distinct id) from q").fetchone()[0]:
        raise SystemExit(f"{query_id} is not unique in the query points")
    if con.sql("select count(*) from q where x is null").fetchone()[0]:
        raise SystemExit("some query points have no coordinates")

    # Each reference point is listed under its own cube and the 26 around it, so an equi-join on
    # the cube finds every pair closer than one cube width.
    con.sql("""
        create table r27 as
        select r.id, r.x, r.y, r.z, r.cx + dx as cx, r.cy + dy as cy, r.cz + dz as cz
        from r, range(-1, 2) a(dx), range(-1, 2) b(dy), range(-1, 2) c(dz)
    """)
    self_clause = "and q.id <> r27.id" if exclude_self else ""
    con.sql(f"""
        create table pairs as
        select q.id,
               2 * asin(least(1.0, sqrt((q.x - r27.x) ^ 2 + (q.y - r27.y) ^ 2 + (q.z - r27.z) ^ 2) / 2))
                 * {EARTH_KM} as km
        from q join r27 using (cx, cy, cz)
        where sqrt((q.x - r27.x) ^ 2 + (q.y - r27.y) ^ 2 + (q.z - r27.z) ^ 2) <= {cell} {self_clause}
    """)

    counts = ", ".join(
        f"count(p.km) filter (where p.km <= {r}) as n_within_{f'{r:g}'.replace('.', '_')}km"
        for r in radii_km
    )
    con.sql(f"""
        create table result as
        select q.id as "{query_id}", {counts}, min(p.km) as nearest_km
        from q left join pairs p using (id)
        group by q.id
    """)

    n_out = con.sql("select count(*) from result").fetchone()[0]
    if n_out != n_query:
        raise SystemExit(f"{n_out} result rows for {n_query} query points")
    n_none = con.sql("select count(*) from result where nearest_km is null").fetchone()[0]
    print(f"query points: {n_query}")
    print(f"reference points: {con.sql('select count(*) from r').fetchone()[0]}")
    print(f"no reference point within {radii_km[-1]:g} km: {n_none}")
    for (col,) in con.sql(
        "select column_name from (describe result) where column_name like 'n_within_%'"
    ).fetchall():
        zero, med, mx = con.sql(
            f"select count(*) filter (where {col} = 0), median({col}), max({col}) from result"
        ).fetchone()
        print(f"{col}: zero {zero}, median {med}, max {mx}")
    con.sql(f"copy (select * from result order by 1) to '{out}' (format parquet)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query")
    p.add_argument("query_id")
    p.add_argument("reference")
    p.add_argument("reference_id")
    p.add_argument("--radii-km", type=float, nargs="+", required=True)
    p.add_argument("--exclude-self", action="store_true")
    p.add_argument("--query-where")
    p.add_argument("--reference-where")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    neighbors(a.query, a.query_id, a.reference, a.reference_id, a.radii_km, a.exclude_self,
              a.query_where, a.reference_where, a.out)

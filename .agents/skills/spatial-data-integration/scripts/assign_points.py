"""Assign each point to the polygon that contains it, falling back to the nearest polygon within a distance.

Every input point is accounted for: contained in exactly one polygon, in several, assigned to the
nearest polygon within --max-km, or left unassigned. The counts are printed; with --out the
assignment is written as Parquet with columns <point id>, <polygon key>, how, km.

Both inputs must be in longitude/latitude. Their CRS names are made the same before joining.

Usage:
    uvx --from 'duckdb>=1.5.5' python assign_points.py POINTS POINT_ID POLYGONS POLYGON_KEY \
        [--max-km 5] [--out assigned.parquet]
"""

import argparse

import duckdb


def assign(points, point_id, polygons, polygon_key, max_km, out):
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    con.sql(
        f"create table pt as select \"{point_id}\" as pid,"
        f" ST_SetCRS(geometry, 'EPSG:4326') as geometry from '{points}'"
    )
    con.sql(
        f"create table pg as select \"{polygon_key}\" as pkey,"
        f" ST_SetCRS(geometry, 'EPSG:4326') as geometry from '{polygons}'"
    )
    n_points = con.sql("select count(*) from pt").fetchone()[0]
    dup_ids = con.sql("select count(*) - count(distinct pid) from pt").fetchone()[0]
    if dup_ids:
        raise SystemExit(f"{point_id} is not unique: {dup_ids} duplicate ids")

    con.sql(
        "create table hit as select pt.pid, pg.pkey from pt join pg"
        " on ST_Intersects(pg.geometry, pt.geometry)"
    )
    con.sql(
        "create table contained as select pid, any_value(pkey) as pkey, count(*) as n"
        " from hit group by pid"
    )

    # Nearest polygon for points in none. ST_Distance_Sphere takes (latitude, longitude),
    # hence the flips; the degree filter only narrows the candidates.
    deg = max_km / 111.0 / 0.2  # generous: a degree of longitude shrinks towards the poles
    con.sql(f"""
        create table nearest as
        select pid, arg_min(pkey, km) as pkey, min(km) as km from (
            select pt.pid, pg.pkey,
                   ST_Distance_Sphere(
                       ST_FlipCoordinates(pt.geometry),
                       ST_FlipCoordinates(ST_ClosestPoint(pg.geometry, pt.geometry))
                   ) / 1000.0 as km
            from pt join pg on ST_DWithin(pg.geometry, pt.geometry, {deg})
            where pt.pid not in (select pid from contained)
        ) where km <= {max_km}
        group by pid
    """)

    con.sql("""
        create table assigned as
        select pid, pkey, case when n = 1 then 'contained' else 'contained_multiple' end as how,
               0.0 as km
        from contained
        union all
        select pid, pkey, 'nearest' as how, km from nearest
        union all
        select pid, null as pkey, 'unassigned' as how, null as km from pt
        where pid not in (select pid from contained) and pid not in (select pid from nearest)
    """)

    counts = dict(con.sql("select how, count(*) from assigned group by 1").fetchall())
    total = sum(counts.values())
    print(f"points: {n_points}")
    for how in ("contained", "contained_multiple", "nearest", "unassigned"):
        print(f"{how}: {counts.get(how, 0)}")
    if total != n_points:
        raise SystemExit(f"accounted for {total} of {n_points} points")
    if counts.get("nearest"):
        q = con.sql(
            "select quantile_cont(km, [0.5, 0.9]), max(km) from assigned where how = 'nearest'"
        ).fetchone()
        print(f"nearest km: median {q[0][0]:.3f}, p90 {q[0][1]:.3f}, max {q[1]:.3f}")

    if out:
        con.sql(
            f"copy (select pid as \"{point_id}\", pkey as \"{polygon_key}\", how, km"
            f" from assigned order by pid) to '{out}' (format parquet)"
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("points")
    p.add_argument("point_id")
    p.add_argument("polygons")
    p.add_argument("polygon_key")
    p.add_argument("--max-km", type=float, default=5.0)
    p.add_argument("--out")
    a = p.parse_args()
    assign(a.points, a.point_id, a.polygons, a.polygon_key, a.max_km, a.out)

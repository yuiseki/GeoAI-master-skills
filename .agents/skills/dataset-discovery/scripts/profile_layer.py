"""Profile one GeoParquet layer: rows, columns, CRS, geometry types, extent, invalid geometries.

Usage:
    uvx --from 'duckdb>=1.5.5' python profile_layer.py <parquet path or hf:// / https:// URL>
"""

import sys

import duckdb


def profile(src: str) -> None:
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    con.sql(f"create table t as select * from '{src}'")

    rows = con.sql("select count(*) from t").fetchone()[0]
    print(f"rows: {rows}")

    cols = con.sql("describe t").fetchall()
    print(f"columns: {len(cols)}")
    for name, typ, *_ in cols:
        nulls = con.sql(f'select count(*) - count("{name}") from t').fetchone()[0]
        print(f"  {name}\t{typ}\tnull={nulls}")

    if not any(name == "geometry" for name, *_ in cols):
        print("geometry: no column")
        return
    if con.sql("select count(geometry) from t").fetchone()[0] == 0:
        print("geometry: column present, every value NULL")
        return

    for (crs,) in con.sql("select distinct ST_CRS(geometry) from t").fetchall():
        print(f"crs: {crs}")
    for gtype, n in con.sql(
        "select ST_GeometryType(geometry), count(*) from t group by 1 order by 2 desc"
    ).fetchall():
        print(f"geometry: {gtype} {n}")
    xmin, ymin, xmax, ymax = con.sql(
        "select min(ST_XMin(geometry)), min(ST_YMin(geometry)),"
        " max(ST_XMax(geometry)), max(ST_YMax(geometry)) from t"
    ).fetchone()
    print(f"extent: {xmin} {ymin} {xmax} {ymax}")
    invalid = con.sql("select count(*) from t where not ST_IsValid(geometry)").fetchone()[0]
    print(f"invalid: {invalid}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    profile(sys.argv[1])

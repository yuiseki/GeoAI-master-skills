"""Fetch the pinned inputs for the Koto accident reports into artifacts/_traffic_accident/koto-accident-trends-by-role/.

Run from the repository root:
uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/koto-accident-trends-by-role/scripts/prepare.py

Writes (all EPSG:4326-style lon/lat unless noted):
  tokyo_honhyo.parquet   NPA honhyo rows of Tokyo (police pref 30), 7 file years, with file_year
  wards.parquet          Tokyo 23 wards: code5, name, population 2020, geometry (EPSG:4612 lon/lat)
  towns.parquet          Koto's TOWN_COUNT census small areas: KEY_CODE, S_NAME, HCODE, JINKO, geometry (JGD2000 lon/lat)
  schools.parquet        OSM amenity=school named 小学校/中学校 inside Koto, one point per name
  roads.parquet          OSM highway lines inside Koto's bbox (for the base map), EPSG:4326 lon/lat
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts/_traffic_accident/koto-accident-trends-by-role"
NPA_REV = "389500aae5cec45f1311163f70db6a5f05867838"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
BOUNDARY_REV = "823195c40e1055e2c1b3c0a635369f8c82b6c3fb"
OSM_REV = "38f7a5f961b6e33343d82a11152e768c37d22664"
NPA = f"hf://datasets/yuiseki/npa-traffic-accidents@{NPA_REV}/parquet/*/honhyo.parquet"
ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
TOWNS = f"https://huggingface.co/datasets/yuiseki/estat-boundary-2020/resolve/{BOUNDARY_REV}/parquet/r2ka13.parquet"
OSM = f"hf://datasets/yuiseki/osm-tokyo23-src-2026-08@{OSM_REV}/parquet"
KOTO = "13108"
CITY = KOTO[2:]
HONHYO_ROWS = 205541  # the same file for every ward (taito-accident-trends-by-role EXPERIMENT_TRACKER R001)
# Counted on the first run (2026-11-03) and recorded in EXPERIMENT_TRACKER.md R000; a change means another table.
TOWN_COUNT = 173
TOWN_POPULATION = 524310


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs")

    # The Tokyo honhyo and the 23 wards are the same for every ward project: reuse them when they are there
    # (copied from another ward's artifacts), but always check them.
    if not (OUT / "tokyo_honhyo.parquet").exists():
        con.sql(f"""copy (
            select regexp_extract(filename, 'parquet/([0-9]{{4}})/', 1) as file_year, * exclude (filename, geometry)
            from read_parquet('{NPA}', union_by_name = true, filename = true)
            where "都道府県コード" = '30'
        ) to '{OUT / "tokyo_honhyo.parquet"}' (format parquet)""")
    rows, years = con.execute(f"select count(*), count(distinct file_year) from '{OUT / 'tokyo_honhyo.parquet'}'").fetchall()[0]
    if (rows, years) != (HONHYO_ROWS, 7):
        raise RuntimeError(f"expected {HONHYO_ROWS} rows in 7 file years, got {rows} in {years}")

    if not (OUT / "wards.parquet").exists():
        con.sql(f"""copy (
            select code5, name, population, ST_AsWKB(geometry) as geometry from '{ADMIN}'
            where code5 between '13101' and '13123'
        ) to '{OUT / "wards.parquet"}' (format parquet)""")
    wards = con.execute(f"select count(*) from '{OUT / 'wards.parquet'}'").fetchall()[0][0]
    if wards != 23:
        raise RuntimeError(f"expected 23 wards, got {wards}")

    # HCODE added for Koto: the ward's file has rows without S_NAME, the water (HCODE 8154, 水面) in 16 pieces and a
    # land area (8101) without a name; analyze.py names them and gives the water no rate.
    con.sql(f"""copy (
        select KEY_CODE, S_NAME, HCODE, cast(JINKO as integer) as JINKO, geometry from '{TOWNS}'
        where CITY = '{CITY}' and PREF = '13'
    ) to '{OUT / "towns.parquet"}' (format parquet)""")
    n, pop = con.execute(f"select count(*), sum(JINKO) from '{OUT / 'towns.parquet'}'").fetchall()[0]
    if (n, pop) != (TOWN_COUNT, TOWN_POPULATION):
        raise RuntimeError(f"expected {TOWN_COUNT} towns and {TOWN_POPULATION} people, got {n} and {pop}")

    con.sql(f"""create temp table koto as
        select ST_GeomFromWKB(geometry) as g from '{OUT / "wards.parquet"}' where code5 = '{KOTO}'""")
    # OSM is EPSG:3857; reproject to lon/lat (always_xy) before testing against the ward polygon.
    xmin, ymin, xmax, ymax = con.execute("select ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g) from koto").fetchall()[0]
    con.sql(f"""create temp table school_shapes as
        select name, ST_Transform(ST_Centroid(way), 'EPSG:3857', 'EPSG:4326', always_xy := true) as p
        from '{OSM}/planet_osm_polygon.parquet' where amenity = 'school' and (name like '%小学校' or name like '%中学校')
        union all
        select name, ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true)
        from '{OSM}/planet_osm_point.parquet' where amenity = 'school' and (name like '%小学校' or name like '%中学校')""")
    # One point per name: a school can be several polygons, or a polygon and a node.
    con.sql(f"""copy (
        select name, avg(ST_X(p)) as lon, avg(ST_Y(p)) as lat, count(*) as shapes
        from school_shapes, koto where ST_Contains(koto.g, p) group by name order by name
    ) to '{OUT / "schools.parquet"}' (format parquet)""")

    con.sql(f"""copy (
        select osm_id, highway, name,
               ST_AsWKB(ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true)) as geometry
        from '{OSM}/planet_osm_line.parquet'
        where highway in ('motorway','trunk','primary','secondary','tertiary','unclassified','residential',
                          'living_street','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link')
          and ST_Intersects(ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true),
                            ST_MakeEnvelope({xmin - 0.003}, {ymin - 0.003}, {xmax + 0.003}, {ymax + 0.003}))
    ) to '{OUT / "roads.parquet"}' (format parquet)""")

    for name in ["tokyo_honhyo", "wards", "towns", "schools", "roads"]:
        print(name, con.execute(f"select count(*) from '{OUT / name}.parquet'").fetchall()[0][0])


if __name__ == "__main__":
    main()

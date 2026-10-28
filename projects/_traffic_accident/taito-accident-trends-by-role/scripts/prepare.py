"""Fetch the pinned inputs for the Taito accident reports into artifacts/_traffic_accident/taito-accident-trends-by-role/.

Run from the repository root:
uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/taito-accident-trends-by-role/scripts/prepare.py

Writes (all EPSG:4326-style lon/lat unless noted):
  tokyo_honhyo.parquet   NPA honhyo rows of Tokyo (police pref 30), 7 file years, with file_year
  wards.parquet          Tokyo 23 wards: code5, name, population 2020, geometry (EPSG:4612 lon/lat)
  towns.parquet          Taito's 108 census small areas: KEY_CODE, S_NAME, JINKO, geometry (JGD2000 lon/lat)
  schools.parquet        OSM amenity=school named 小学校/中学校 inside Taito, one point per name
  roads.parquet          OSM highway lines inside Taito's bbox (for the base map), EPSG:4326 lon/lat
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts/_traffic_accident/taito-accident-trends-by-role"
NPA_REV = "389500aae5cec45f1311163f70db6a5f05867838"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
BOUNDARY_REV = "823195c40e1055e2c1b3c0a635369f8c82b6c3fb"
OSM_REV = "38f7a5f961b6e33343d82a11152e768c37d22664"
NPA = f"hf://datasets/yuiseki/npa-traffic-accidents@{NPA_REV}/parquet/*/honhyo.parquet"
ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
TOWNS = f"https://huggingface.co/datasets/yuiseki/estat-boundary-2020/resolve/{BOUNDARY_REV}/parquet/r2ka13.parquet"
OSM = f"hf://datasets/yuiseki/osm-tokyo23-src-2026-08@{OSM_REV}/parquet"
TAITO = "13106"
TOWN_COUNT = 108
TOWN_POPULATION = 211444


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs")

    con.sql(f"""copy (
        select regexp_extract(filename, 'parquet/([0-9]{{4}})/', 1) as file_year, * exclude (filename, geometry)
        from read_parquet('{NPA}', union_by_name = true, filename = true)
        where "都道府県コード" = '30'
    ) to '{OUT / "tokyo_honhyo.parquet"}' (format parquet)""")
    years = con.execute(f"select count(distinct file_year) from '{OUT / 'tokyo_honhyo.parquet'}'").fetchall()[0][0]
    if years != 7:
        raise RuntimeError(f"expected 7 file years, got {years}")

    con.sql(f"""copy (
        select code5, name, population, ST_AsWKB(geometry) as geometry from '{ADMIN}'
        where code5 between '13101' and '13123'
    ) to '{OUT / "wards.parquet"}' (format parquet)""")
    wards = con.execute(f"select count(*) from '{OUT / 'wards.parquet'}'").fetchall()[0][0]
    if wards != 23:
        raise RuntimeError(f"expected 23 wards, got {wards}")

    con.sql(f"""copy (
        select KEY_CODE, S_NAME, cast(JINKO as integer) as JINKO, geometry from '{TOWNS}'
        where CITY = '106' and PREF = '13'
    ) to '{OUT / "towns.parquet"}' (format parquet)""")
    n, pop = con.execute(f"select count(*), sum(JINKO) from '{OUT / 'towns.parquet'}'").fetchall()[0]
    if (n, pop) != (TOWN_COUNT, TOWN_POPULATION):
        raise RuntimeError(f"expected {TOWN_COUNT} towns and {TOWN_POPULATION} people, got {n} and {pop}")

    con.sql(f"""create temp table taito as
        select ST_GeomFromWKB(geometry) as g from '{OUT / "wards.parquet"}' where code5 = '{TAITO}'""")
    # OSM is EPSG:3857; reproject to lon/lat (always_xy) before testing against the ward polygon.
    xmin, ymin, xmax, ymax = con.execute("select ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g) from taito").fetchall()[0]
    con.sql(f"""create temp table school_shapes as
        select name, ST_Transform(ST_Centroid(way), 'EPSG:3857', 'EPSG:4326', always_xy := true) as p
        from '{OSM}/planet_osm_polygon.parquet' where amenity = 'school' and (name like '%小学校' or name like '%中学校')
        union all
        select name, ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true)
        from '{OSM}/planet_osm_point.parquet' where amenity = 'school' and (name like '%小学校' or name like '%中学校')""")
    # One point per name: a school can be several polygons, or a polygon and a node.
    con.sql(f"""copy (
        select name, avg(ST_X(p)) as lon, avg(ST_Y(p)) as lat, count(*) as shapes
        from school_shapes, taito where ST_Contains(taito.g, p) group by name order by name
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

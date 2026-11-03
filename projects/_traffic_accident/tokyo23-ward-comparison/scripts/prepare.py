"""Fetch the pinned inputs for the 23-ward comparison into artifacts/_traffic_accident/tokyo23-ward-comparison/.

Run from the repository root:
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/tokyo23-ward-comparison/scripts/prepare.py

Writes:
  tokyo_honhyo.parquet   NPA honhyo rows of Tokyo (police pref 30), 7 file years, with file_year (as the ward projects)
  wards.parquet          Tokyo 23 wards: code5, name, population 2020, geometry (EPSG:4612 lon/lat, as the ward projects)
  towns.parquet          census small-area rows of the 23 wards: CITY, KEY_CODE, S_NAME, HCODE, JINKO, geometry
  ward_roads.csv         OSM car-road length (km) inside each ward, the highway classes of the ward projects
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts/_traffic_accident" / Path(__file__).resolve().parents[1].name
NPA_REV = "389500aae5cec45f1311163f70db6a5f05867838"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
BOUNDARY_REV = "823195c40e1055e2c1b3c0a635369f8c82b6c3fb"
OSM_REV = "38f7a5f961b6e33343d82a11152e768c37d22664"
NPA = f"hf://datasets/yuiseki/npa-traffic-accidents@{NPA_REV}/parquet/*/honhyo.parquet"
ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
TOWNS = f"https://huggingface.co/datasets/yuiseki/estat-boundary-2020/resolve/{BOUNDARY_REV}/parquet/r2ka13.parquet"
OSM = f"hf://datasets/yuiseki/osm-tokyo23-src-2026-08@{OSM_REV}/parquet"
HONHYO_ROWS = 205541  # as the ward projects (taito EXPERIMENT_TRACKER R001)
TOWN_ROWS = 3192  # the 23 wards in r2ka13 (dataset-discovery estat-boundary-2020, counted 2026-11-03)
# The car roads of the ward projects' road length (their prepare.py), motorways included as there.
HIGHWAYS = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
            "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs")
    con.sql("set memory_limit='6GB'; set threads=4")

    # The same SQL as the ward projects' prepare.py; reused when copied from a ward project, but always checked.
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
    if con.execute(f"select count(*) from '{OUT / 'wards.parquet'}'").fetchall()[0][0] != 23:
        raise RuntimeError("expected 23 wards")

    con.sql(f"""copy (
        select CITY, KEY_CODE, S_NAME, HCODE, cast(JINKO as integer) as JINKO, geometry from '{TOWNS}'
        where PREF = '13' and CITY between '101' and '123'
    ) to '{OUT / "towns.parquet"}' (format parquet)""")
    n = con.execute(f"select count(*) from '{OUT / 'towns.parquet'}'").fetchall()[0][0]
    if n != TOWN_ROWS:
        raise RuntimeError(f"expected {TOWN_ROWS} small-area rows, got {n}")

    # Road length inside each ward polygon, in EPSG:6677 metres. OSM is EPSG:3857 (always_xy to lon/lat first).
    con.sql("set geometry_always_xy = true")
    con.sql(f"""create temp table w as select substr(code5, 3) as code,
        ST_Transform(ST_GeomFromWKB(geometry), 'EPSG:4612', 'EPSG:6677') as g from '{OUT / 'wards.parquet'}'""")
    inlist = ", ".join(f"'{h}'" for h in HIGHWAYS)
    con.sql(f"""create temp table r as select
        ST_Transform(ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true), 'OGC:CRS84', 'EPSG:6677') as g
        from '{OSM}/planet_osm_line.parquet' where highway in ({inlist})""")
    con.sql(f"""copy (select w.code, round(sum(ST_Length(ST_Intersection(r.g, w.g))) / 1000, 3) as road_km
        from w join r on ST_Intersects(r.g, w.g) group by w.code order by w.code) to '{OUT / 'ward_roads.csv'}'
        (header, delimiter ',')""")
    roads = con.execute(f"select count(*), sum(road_km) from '{OUT / 'ward_roads.csv'}'").fetchall()[0]
    if roads[0] != 23:
        raise RuntimeError(f"road length for {roads[0]} wards, expected 23")
    for name in ["tokyo_honhyo", "wards", "towns"]:
        print(name, con.execute(f"select count(*) from '{OUT / name}.parquet'").fetchall()[0][0])
    print("ward_roads", roads)


if __name__ == "__main__":
    main()

"""Fetch inputs for Chiyoda accident analysis into artifacts/_traffic_accident/chiyoda-accident-trends-by-role/.

Run from repository root:
uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/chiyoda-accident-trends-by-role/scripts/prepare.py
"""

from pathlib import Path
import tempfile
import time
import urllib.request
import duckdb

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts/_traffic_accident/chiyoda-accident-trends-by-role"
NPA_REV = "389500aae5cec45f1311163f70db6a5f05867838"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
BOUNDARY_REV = "823195c40e1055e2c1b3c0a635369f8c82b6c3fb"
OSM_REV = "38f7a5f961b6e33343d82a11152e768c37d22664"

YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
CHIYODA = "13101"
TOWN_COUNT = 115
TOWN_POPULATION = 66680

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
}


def download_file(url: str, dest: Path, max_retries: int = 10, chunk_size: int = 1024 * 1024):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
            print(f"Downloaded {dest.name} ({dest.stat().st_size} bytes)")
            return
        except Exception as e:
            if dest.exists():
                dest.unlink(missing_ok=True)
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to download {url}: {e}")
            time.sleep(2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cache_dir = OUT / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.sql("install spatial; load spatial;")

    # 1. Download and filter Tokyo honhyo for 7 years
    tokyo_year_files = []
    for y in YEARS:
        url = f"https://huggingface.co/datasets/yuiseki/npa-traffic-accidents/resolve/{NPA_REV}/parquet/{y}/honhyo.parquet"
        raw_path = cache_dir / f"honhyo_{y}.parquet"
        download_file(url, raw_path)
        
        tokyo_y_path = cache_dir / f"tokyo_{y}.parquet"
        if not tokyo_y_path.exists():
            con.sql(f"""copy (
                select '{y}' as file_year, * exclude (geometry)
                from read_parquet('{raw_path.as_posix()}')
                where "都道府県コード" = '30'
            ) to '{tokyo_y_path.as_posix()}' (format parquet)""")
        tokyo_year_files.append(f"'{tokyo_y_path.as_posix()}'")

    con.sql(f"""copy (
        select * from read_parquet([{", ".join(tokyo_year_files)}], union_by_name = true)
    ) to '{(OUT / "tokyo_honhyo.parquet").as_posix()}' (format parquet)""")
    years = con.execute(f"select count(distinct file_year) from '{(OUT / 'tokyo_honhyo.parquet').as_posix()}'").fetchall()[0][0]
    if years != 7:
        raise RuntimeError(f"expected 7 file years, got {years}")

    # 2. Municipalities (wards)
    admin_url = f"https://huggingface.co/datasets/yuiseki/jp-admin-2026-09/resolve/{ADMIN_REV}/municipalities.parquet"
    admin_path = cache_dir / "municipalities.parquet"
    download_file(admin_url, admin_path)

    con.sql(f"""copy (
        select code5, name, population, ST_AsWKB(geometry) as geometry from '{admin_path.as_posix()}'
        where code5 between '13101' and '13123'
    ) to '{(OUT / "wards.parquet").as_posix()}' (format parquet)""")
    wards = con.execute(f"select count(*) from '{(OUT / 'wards.parquet').as_posix()}'").fetchall()[0][0]
    if wards != 23:
        raise RuntimeError(f"expected 23 wards, got {wards}")

    # 3. Towns (census small areas)
    towns_url = f"https://huggingface.co/datasets/yuiseki/estat-boundary-2020/resolve/{BOUNDARY_REV}/parquet/r2ka13.parquet"
    towns_path = cache_dir / "r2ka13.parquet"
    download_file(towns_url, towns_path)

    con.sql(f"""copy (
        select KEY_CODE, S_NAME, sum(cast(JINKO as integer)) as JINKO,
               ST_AsWKB(ST_Union_Agg(ST_GeomFromWKB(geometry))) as geometry
        from '{towns_path.as_posix()}'
        where CITY = '101' and PREF = '13'
        group by KEY_CODE, S_NAME
    ) to '{(OUT / "towns.parquet").as_posix()}' (format parquet)""")
    n, pop = con.execute(f"select count(*), sum(JINKO) from '{(OUT / 'towns.parquet').as_posix()}'").fetchall()[0]
    if (n, pop) != (TOWN_COUNT, TOWN_POPULATION):
        raise RuntimeError(f"expected {TOWN_COUNT} towns and {TOWN_POPULATION} people, got {n} and {pop}")

    # 4. OSM Schools & Roads
    con.sql(f"""create temp table chiyoda as
        select ST_GeomFromWKB(geometry) as g from '{(OUT / "wards.parquet").as_posix()}' where code5 = '{CHIYODA}'""")
    xmin, ymin, xmax, ymax = con.execute("select ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g) from chiyoda").fetchall()[0]

    for part in ["polygon", "point", "line"]:
        osm_url = f"https://huggingface.co/datasets/yuiseki/osm-tokyo23-src-2026-08/resolve/{OSM_REV}/parquet/planet_osm_{part}.parquet"
        download_file(osm_url, cache_dir / f"planet_osm_{part}.parquet")

    con.sql(f"""create temp table school_shapes as
        select name, ST_Transform(ST_Centroid(way), 'EPSG:3857', 'EPSG:4326', always_xy := true) as p
        from '{(cache_dir / "planet_osm_polygon.parquet").as_posix()}' where amenity = 'school' and (name like '%小学校' or name like '%中学校')
        union all
        select name, ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true)
        from '{(cache_dir / "planet_osm_point.parquet").as_posix()}' where amenity = 'school' and (name like '%小学校' or name like '%中学校')""")

    con.sql(f"""copy (
        select name, avg(ST_X(p)) as lon, avg(ST_Y(p)) as lat, count(*) as shapes
        from school_shapes, chiyoda where ST_Contains(chiyoda.g, p) group by name order by name
    ) to '{(OUT / "schools.parquet").as_posix()}' (format parquet)""")

    con.sql(f"""copy (
        select osm_id, highway, name,
               ST_AsWKB(ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true)) as geometry
        from '{(cache_dir / "planet_osm_line.parquet").as_posix()}'
        where highway in ('motorway','trunk','primary','secondary','tertiary','unclassified','residential',
                          'living_street','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link')
          and ST_Intersects(ST_Transform(way, 'EPSG:3857', 'EPSG:4326', always_xy := true),
                            ST_MakeEnvelope({xmin - 0.003}, {ymin - 0.003}, {xmax + 0.003}, {ymax + 0.003}))
    ) to '{(OUT / "roads.parquet").as_posix()}' (format parquet)""")

    for name in ["tokyo_honhyo", "wards", "towns", "schools", "roads"]:
        print(name, con.execute(f"select count(*) from '{(OUT / name).as_posix()}.parquet'").fetchall()[0][0])


if __name__ == "__main__":
    main()

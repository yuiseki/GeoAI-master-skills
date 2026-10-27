"""Count the 23-ward mesh universe, population rows and shelter supply before ranking.

Run: uvx --with 'duckdb>=1.5.5' python scripts/recon.py
"""

import duckdb

MLIT = "hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet"
CENSUS = "hf://datasets/yuiseki/estat-census-mesh-2020@6c486c8649484e09e549c0c99b5fa89b4f416edb/parquet/T001140.parquet"
SITES = "hf://datasets/yuiseki/gsi-evacuation-sites-jp@d8ad2169789b71c951e8808b2e54a953030aae07/parquet/sites.parquet"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET geometry_always_xy = true;")

print("duckdb", duckdb.__version__)

print("\n-- wards")
print(con.sql(f"""
    select count(*) as wards, sum(population) as census_pop
    from read_parquet('{ADMIN}') where code5 between '13101' and '13123'
"""))

print("\n-- mesh grid (2020 attribute) and center-in-ward universe")
print(con.sql(f"""
    with w as (
      select geometry from read_parquet('{ADMIN}') where code5 between '13101' and '13123'
    ), m as (
      select mesh1kmid, cast(lon_center as double) lon, cast(lat_center as double) lat, citycode
      from read_parquet('{MLIT}/attribute_mesh1km.parquet') where version = '2020'
    )
    select
      (select count(*) from m) as all_mesh,
      (select count(*) from m where citycode between '13101' and '13123') as by_citycode,
      (select count(distinct mesh1kmid) from m
        where exists (select 1 from w where ST_Within(ST_SetCRS(ST_Point(lon, lat), 'EPSG:4612'), w.geometry))) as center_in_ward
"""))

print("\n-- census rows and total, mesh keyed")
print(con.sql(f"""
    select count(*) rows, count(distinct KEY_CODE) meshes,
           sum(try_cast(T001140001 as bigint)) total
    from read_parquet('{CENSUS}')
"""))

print("\n-- daytime population rows (Oct, weekday, 11-14) for Tokyo")
print(con.sql(f"""
    select year, count(*) rows, count(distinct mesh1kmid) meshes, sum(population) total, min(population) mn
    from read_parquet('{MLIT}/monthly_mdp_mesh1km.parquet')
    where prefcode = '13' and month = '10' and dayflag = '1' and timezone = '0'
      and year in ('2019', '2021')
    group by year order by year
"""))

print("\n-- evacuation sites")
print(con.sql(f"""
    select count(*) all_sites,
           count(*) filter (where earthquake) eq_sites,
           count(*) filter (where earthquake and substr(common_id, 2, 5) between '13101' and '13123') eq_tokyo23
    from read_parquet('{SITES}')
"""))

print("\n-- site counts within 1 km of each in-ward mesh center (distribution)")
print(con.sql(f"""
    with w as (
      select geometry from read_parquet('{ADMIN}') where code5 between '13101' and '13123'
    ), m as (
      select mesh1kmid, cast(lon_center as double) lon, cast(lat_center as double) lat
      from read_parquet('{MLIT}/attribute_mesh1km.parquet') where version = '2020'
    ), mw as (
      select distinct mesh1kmid, ST_Transform(ST_SetCRS(ST_Point(lon, lat), 'EPSG:4612'), 'EPSG:6677') g
      from m where exists (select 1 from w where ST_Within(ST_SetCRS(ST_Point(lon, lat), 'EPSG:4612'), w.geometry))
    ), s as (
      select ST_Transform(geometry, 'EPSG:6677') g
      from read_parquet('{SITES}') where earthquake
    )
    select count(*) meshes_without_site_1km, avg(n) mean_sites, median(n) median_sites, max(n) max_sites
    from (
      select mw.mesh1kmid, count(s.g) as n
      from mw left join s on ST_DWithin(mw.g, s.g, 1000)
      group by mw.mesh1kmid
    )
"""))

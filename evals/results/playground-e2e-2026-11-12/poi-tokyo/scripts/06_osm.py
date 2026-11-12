"""OSM (2026-08-31 freeze) shop=convenience points in the 23 wards, for cross-checking."""
import duckdb
A="/work/artifacts/tokyo23-convenience-stores/"
c=duckdb.connect(); c.sql("SET threads=8; install spatial; load spatial; install httpfs; load httpfs")
u="hf://datasets/yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664/parquet/planet_osm_point.parquet"
print([r[0] for r in c.execute(f"describe select * from read_parquet('{u}')").fetchall()])
c.execute(f"""create table o as select osm_id, name, brand, shop, ST_X(ST_Transform(way,'EPSG:3857','EPSG:4326',always_xy:=true)) lon, ST_Y(ST_Transform(way,'EPSG:3857','EPSG:4326',always_xy:=true)) lat
  from read_parquet('{u}') where shop='convenience'""")
c.execute(f"create table w as select region_id, region_name, geometry g from read_parquet('{A}wards.parquet')")
c.execute(f"copy (select o.*, w.region_id from o join w on st_contains(w.g, st_point(o.lon,o.lat))) to '{A}osm_cvs.parquet'")
print(c.execute("select count(*) from o").fetchall(), c.execute(f"select count(*), count(brand) from read_parquet('{A}osm_cvs.parquet')").fetchall())
c.execute(f"""copy (select name, ST_X(ST_Transform(way,'EPSG:3857','EPSG:4326',always_xy:=true)) lon, ST_Y(ST_Transform(way,'EPSG:3857','EPSG:4326',always_xy:=true)) lat
  from read_parquet('{u}') where railway in ('station','halt') and name is not null) to '{A}osm_stations.parquet'""")
print(c.execute(f"select count(*) from read_parquet('{A}osm_stations.parquet')").fetchall())

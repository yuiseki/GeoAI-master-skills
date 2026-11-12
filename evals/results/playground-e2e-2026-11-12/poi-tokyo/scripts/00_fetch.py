"""Fetch the 23 wards (jp-admin-2026-09) and copy them once."""
import duckdb
c = duckdb.connect(); c.sql("SET threads=8; install spatial; load spatial; install httpfs; load httpfs")
src="hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
print(c.sql(f"describe select * from read_parquet('{src}')").fetchall())
c.sql(f"""copy (select code5, name, population, households, geometry_source, ST_AsWKB(geometry) g0 from read_parquet('{src}')
 where code5 between '13101' and '13123') to '/work/artifacts/tokyo23-convenience-stores/wards_raw.parquet'""")
print(c.sql("select code5,name,population from read_parquet('/work/artifacts/tokyo23-convenience-stores/wards_raw.parquet') order by 1").fetchall())

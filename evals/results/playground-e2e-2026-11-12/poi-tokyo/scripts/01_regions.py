import duckdb
c = duckdb.connect(); c.sql("install spatial; load spatial")
A="/work/artifacts/tokyo23-convenience-stores/"
c.sql(f"""copy (select code5 region_id, name region_name, population, households, geometry
 from read_parquet('hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet')
 where code5 between '13101' and '13123' order by code5) to '{A}wards.parquet' (format parquet)""")
print(c.sql(f"select count(*), sum(population), min(st_xmin(geometry)),max(st_xmax(geometry)),min(st_ymin(geometry)),max(st_ymax(geometry)), bool_and(st_isvalid(geometry)) from read_parquet('{A}wards.parquet')").fetchall())

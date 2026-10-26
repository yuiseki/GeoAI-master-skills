import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load spatial'); c.sql('set geometry_always_xy=true')
print(c.sql("describe 'data/kontur.parquet'").fetchall())
print(c.sql("select count(*), sum(population), min(population), median(population) from 'data/kontur.parquet'").fetchall())
c.sql("""create or replace table hex as
 select h3, population pop, ST_Centroid(ST_SetCRS(ST_Transform(ST_SetCRS(geometry,'EPSG:3857'),'EPSG:3857','OGC:CRS84'),'OGC:CRS84')) ctr from 'data/kontur.parquet'""")
print(c.sql("select ST_AsText(ctr) from hex limit 3").fetchall())

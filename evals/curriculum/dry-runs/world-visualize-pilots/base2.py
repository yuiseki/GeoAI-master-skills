import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load spatial'); c.sql('set geometry_always_xy=true')
c.sql("create or replace table ne as select ADM0_A3 a3, ISO_A3_EH iso3, NAME_JA name_ja, ST_SetCRS(geometry,'OGC:CRS84') g from 'data/ne0.parquet'")
c.sql("create or replace table hexc as select h.h3, h.pop, h.ctr, ne.iso3, ne.a3 from hex h left join ne on ST_Intersects(ne.g, h.ctr)")
print(c.sql("select count(*), count(distinct h3), sum(pop) filter (where a3 is null)/1e6 unassigned_m, count(*) filter (where a3 is null) from hexc").fetchall())
# nearest country for unassigned
c.sql("""create or replace table hexn as
 with u as (select h3, pop, ctr from hexc where a3 is null)
 select u.h3, arg_min(ne.a3, ST_Distance(ne.g,u.ctr)) a3, min(ST_Distance(ne.g,u.ctr)) d from u, ne group by u.h3""")
print(c.sql("select count(*), quantile_cont(d,[0.5,0.9,1]) from hexn").fetchall())
c.sql("""create or replace table hexcty as select c.h3, c.pop, c.ctr, coalesce(c.a3, n.a3) a3, c.a3 is null nearest from hexc c left join hexn n using (h3)""")
print(c.sql("select count(*), count(distinct h3), sum(pop)/1e9 from hexcty").fetchall())

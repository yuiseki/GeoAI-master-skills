# Pilot C: share of population in H3 r4 cells with no OpenCelliD cell record (in the cell or k=1 ring), vs WDI mobile subscriptions.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load h3')
print(c.sql("select count(*), count(distinct mcc), min(to_timestamp(updated)::date), max(to_timestamp(updated)::date), count(*) filter (where samples<=1) from 'data/ocid.parquet'").fetchall())
print(c.sql("select radio, count(*) from 'data/ocid.parquet' group by 1 order by 2 desc").fetchall())
c.sql("create or replace table oc as select h3_latlng_to_cell_string(lat, lon, 4) h3, count(*) n, max(to_timestamp(updated)::date) last from 'data/ocid.parquet' where lat between -90 and 90 group by 1")
c.sql("""create or replace table cov as select h.a3, h.h3, h.pop, coalesce(o.n,0) n,
   exists (select 1 from oc o2 where o2.h3 in (select unnest(h3_grid_disk(h.h3,1)))) ring1
   from hexcty h left join oc o using (h3)""")
print(c.sql("select round(sum(pop) filter (where n=0)/1e6) no_cell_m, round(sum(pop) filter (where not ring1)/1e6) no_ring_m from cov").fetchall())
c.sql("""create or replace table gap as select a3, sum(pop) pop, sum(pop) filter (where n=0)/sum(pop) gap0, sum(pop) filter (where not ring1)/sum(pop) gap1 from cov group by 1""")
c.sql("""create or replace table w as select country_code a3, arg_max(value, year) cel, max(year) y from 'data/wdi.parquet' where indicator_code='IT.CEL.SETS.P2' and value is not null group by 1""")
print(c.sql("select count(*), corr(gap0, cel), corr(gap0, ln(cel)) from gap join w using (a3) where pop>1e6").fetchall())
print('high subs but big gap', c.sql("select a3, round(pop/1e6) pop_m, round(gap0,2), round(cel) from gap join w using (a3) where pop>5e6 and cel>100 order by gap0 desc limit 10").fetchall())
print('largest gap', c.sql("select a3, round(pop/1e6) pop_m, round(gap0,2), round(gap1,2), round(cel) from gap left join w using (a3) where pop>5e6 order by gap0 desc limit 10").fetchall())

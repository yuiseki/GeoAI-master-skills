# Pilot W2b: H3 ring distance from each populated cell to the nearest scheduled-service airport, and its residual given density and income.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load h3')
c.sql("create or replace table sc as select distinct cell h3 from ap where scheduled_service='yes'")
c.sql("create or replace table dist as select h3, 0 k from sc")
for k in range(1,16):
    c.sql(f"insert into dist select x.h3, {k} from (select distinct unnest(h3_grid_disk(h3,{k})) h3 from sc) x where x.h3 not in (select h3 from dist)")
c.sql("create or replace table d2 as select h.h3, h.a3, h.pop, coalesce(min(d.k),16) k from hexcty h left join dist d using (h3) group by all")
print(c.sql("select count(*), count(*) filter (where k=16), round(sum(pop) filter (where k>=5)/1e6) far5_m from d2").fetchall())
c.sql("""create or replace table m as select d2.*, ln(pop) lp, ln(g.gdppc) lg, ln(k+1) lk from d2 join gdp g using (a3) where pop>=1000""")
print(c.sql("select count(*), regr_r2(lk, lp), corr(lk, lg) from m").fetchall())
c.sql("""create or replace table res as select *, lk - (regr_intercept(lk, lp) over () + regr_slope(lk, lp) over () * lp) r from m""")
print('populous cells farthest above expectation', c.sql("select a3, h3, round(pop/1e3) pop_k, k, round(r,2) from res where pop>=3e5 order by r desc limit 12").fetchall())
print('by country, pop-weighted residual', c.sql("select a3, round(sum(pop)/1e6) pop_m, round(sum(pop*r)/sum(pop),2) r from res group by 1 having sum(pop)>1e7 order by 3 desc limit 10").fetchall())

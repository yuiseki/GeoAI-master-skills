# Pilot W7: population inside registered GTFS feed bounding boxes, by country, against population and income.
# Input: data/feeds_v2.csv (Mobility Database, sha256 0d90eb4e..., Last-Modified 2026-10-20).
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load spatial'); c.sql('load h3'); c.sql('set geometry_always_xy=true')
c.sql("""create or replace table feeds as select id, data_type, "location.country_code" cc, is_official, status, "urls.authentication_type" auth,
  try_cast("location.bounding_box.minimum_latitude" as double) s, try_cast("location.bounding_box.maximum_latitude" as double) n,
  try_cast("location.bounding_box.minimum_longitude" as double) w, try_cast("location.bounding_box.maximum_longitude" as double) e
  from read_csv('data/feeds_v2.csv', all_varchar=true)""")
print(c.sql("select data_type, status, count(*) from feeds group by all order by 3 desc").fetchall())
c.sql("""create or replace table g as select *, (e-w)*(n-s) deg2 from feeds where data_type='gtfs' and coalesce(status,'') not in ('deprecated','inactive') and s is not null and n>s and e>w""")
print(c.sql("select count(*), count(distinct cc), quantile_cont(deg2,[0.5,0.9,0.99]), max(deg2) from g").fetchall())
# ISO2 -> ISO3 via Natural Earth
c.sql("create or replace table iso as select ISO_A2_EH iso2, ISO_A3_EH iso3 from 'data/ne0.parquet' where ISO_A2_EH<>'-99'")
for name,cap in (('all',1e9),('cap25',25.0)):
    c.sql(f"""create or replace table cov_{name} as select distinct h.h3 from hexcty h, g
      where g.deg2<={cap} and ST_Y(h.ctr) between g.s and g.n and ST_X(h.ctr) between g.w and g.e""")
c.sql("create or replace table gdp as select country_code a3, arg_max(value, year) gdppc from 'data/wdi.parquet' where indicator_code='NY.GDP.PCAP.CD' and value is not null group by 1")
c.sql("""create or replace table cty as select h.a3, sum(h.pop) pop, sum(h.pop) filter (where h.h3 in (select h3 from cov_all)) in_all,
  sum(h.pop) filter (where h.h3 in (select h3 from cov_cap25)) in_cap from hexcty h group by 1""")
c.sql("create or replace table nfeeds as select i.iso3 a3, count(*) n, count(*) filter (where is_official='True') n_off from g join iso i on i.iso2=g.cc group by 1")
print('world share in bbox', c.sql("select round(sum(in_all)/sum(pop),3), round(sum(in_cap)/sum(pop),3) from cty").fetchall())
print('corr share vs ln gdppc', c.sql("select count(*), corr(in_cap/pop, ln(gdppc)), corr(ln(coalesce(n,0)+1), ln(gdppc)) from cty join gdp using (a3) left join nfeeds using (a3) where pop>5e6").fetchall())
c.sql("""create or replace table fit as select a3, pop, gdppc, coalesce(in_cap,0)/pop share, coalesce(n,0) n,
  regr_intercept(coalesce(in_cap,0)/pop, ln(gdppc)) over () + regr_slope(coalesce(in_cap,0)/pop, ln(gdppc)) over () * ln(gdppc) expected
  from cty join gdp using (a3) left join nfeeds using (a3) where pop>5e6""")
print('below expected', c.sql("select a3, round(pop/1e6) pop_m, round(gdppc) gdppc, round(share,2) share, round(expected,2) exp, n from fit order by share-expected limit 10").fetchall())
print('above expected', c.sql("select a3, round(pop/1e6) pop_m, round(gdppc) gdppc, round(share,2) share, round(expected,2) exp, n from fit order by share-expected desc limit 8").fetchall())

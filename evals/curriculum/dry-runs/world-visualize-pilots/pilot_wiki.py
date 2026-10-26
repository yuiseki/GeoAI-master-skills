# Pilot D: geotagged Wikipedia articles (en, ja) per person on H3 r4 cells and by country, vs GDP per capita.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load h3')
print(c.sql("select gt_globe, count(*) from 'data/wiki_coords.parquet' group by 1 order by 2 desc limit 5").fetchall())
print(c.sql("select gt_type, count(*) from 'data/wiki_coords.parquet' group by 1 order by 2 desc limit 12").fetchall())
c.sql("""create or replace table wk as select case when filename like '%.ja/%' then 'ja' else 'en' end lang, gt_type,
  h3_latlng_to_cell_string(lat, lon, 4) h3 from 'data/wiki_coords.parquet' where coalesce(gt_globe,'earth') in ('earth','') and lat between -90 and 90""")
c.sql("create or replace table wkc as select lang, h3, count(*) n, count(*) filter (where gt_type is null or gt_type not in ('country','adm1st','adm2nd','adm3rd','city','isle')) n_nonadmin from wk group by all")
print(c.sql("select lang, sum(n), sum(n) filter (where h3 in (select h3 from hexcty)) in_pop, round(1-sum(n) filter (where h3 in (select h3 from hexcty))/sum(n),3) outside_share from wkc group by 1").fetchall())
c.sql("""create or replace table wkcty as select h.a3, sum(h.pop) pop, sum(coalesce(e.n,0)) en, sum(coalesce(j.n,0)) ja, sum(coalesce(e.n_nonadmin,0)) en_na
  from hexcty h left join (select * from wkc where lang='en') e using (h3) left join (select * from wkc where lang='ja') j using (h3) group by 1""")
c.sql("create or replace table gdp as select country_code a3, arg_max(value, year) g from 'data/wdi.parquet' where indicator_code='NY.GDP.PCAP.CD' and value is not null group by 1")
print(c.sql("select count(*), corr(ln(en/pop*1e6+1), ln(g)), corr(ln(ja/pop*1e6+1), ln(g)) from wkcty join gdp using (a3) where pop>1e6").fetchall())
print('en per million, lowest large countries', c.sql("select a3, round(pop/1e6) pop_m, round(en/pop*1e6,1) en_pm, round(ja/pop*1e6,1) ja_pm from wkcty where pop>3e7 order by en/pop limit 8").fetchall())
print('en per million, highest large', c.sql("select a3, round(pop/1e6) pop_m, round(en/pop*1e6,1) en_pm from wkcty where pop>3e7 order by en/pop desc limit 6").fetchall())
print('rank corr en vs en_nonadmin', c.sql("select corr(r1,r2) from (select rank() over (order by en/pop) r1, rank() over (order by en_na/pop) r2 from wkcty where pop>1e6)").fetchall())

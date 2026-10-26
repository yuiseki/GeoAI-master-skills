# Pilot B: population in H3 r4 cells within k rings of lethal UCDP GED events 2021-2025, by location precision.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load h3')
c.sql("""create or replace table ev as select id, year, where_prec, best, country_id, latitude, longitude,
  h3_latlng_to_cell_string(latitude, longitude, 4) cell from 'data/ucdp.parquet' where year between 2021 and 2025 and best>0""")
print(c.sql("select count(*), sum(best), count(*) filter (where where_prec<=2), sum(best) filter (where where_prec<=2) from ev").fetchall())
print(c.sql("select where_prec, count(*), sum(best) from ev group by 1 order by 1").fetchall())
res={}
for name,cond in (('all','true'),('prec2','where_prec<=2')):
  for k in (0,1):
    t=f"c_{name}_{k}"
    c.sql(f"""create or replace table {t} as
      with s as (select distinct unnest(h3_grid_disk(cell,{k})) h3 from ev where {cond})
      select h.a3, sum(h.pop)/1e6 pop_m from s join hexcty h using (h3) group by 1""")
    res[t]=c.sql(f"select round(sum(pop_m)), list(a3 order by pop_m desc)[1:10] from {t}").fetchall()[0]
    print(t,res[t])
print(c.sql("""select a3, round(a.pop_m,1) all1, round(p.pop_m,1) prec2_1, round(1-coalesce(p.pop_m,0)/a.pop_m,2) lost
  from c_all_1 a left join c_prec2_1 p using (a3) order by a.pop_m desc limit 15""").fetchall())

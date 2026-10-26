# Pilot A: population in H3 r4 cells within k rings of a 1980-2025 IBTrACS point at >=64 kt, by wind source and k.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load h3')
print(c.sql("select count(*), count(USA_WIND), count(WMO_WIND), count(USA_R64_NE), count(distinct SID) from 'data/ibtracs.parquet' where year(ISO_TIME) between 1980 and 2025").fetchall())
print(c.sql("select BASIN, any_value(WMO_AGENCY), count(*), count(WMO_WIND), count(USA_WIND), count(*) filter (where try_cast(WMO_WIND as double)>=64), count(*) filter (where try_cast(USA_WIND as double)>=64) from 'data/ibtracs.parquet' group by 1 order by 3 desc").fetchall())
c.sql("""create or replace table tp as select SID, year(ISO_TIME) y, try_cast(USA_WIND as double) usa, try_cast(WMO_WIND as double) wmo,
  h3_latlng_to_cell_string(LAT, LON, 4) cell from 'data/ibtracs.parquet' where year(ISO_TIME) between 1980 and 2025""")
res={}
for src in ('usa','wmo'):
  for k in (1,2):
    t=f"e_{src}_{k}"
    c.sql(f"""create or replace table {t} as
      with s as (select distinct SID, unnest(h3_grid_disk(cell,{k})) h3 from tp where {src}>=64),
      n as (select h3, count(distinct SID) storms from s group by 1)
      select h.a3, sum(h.pop)/1e6 pop_m, sum(h.pop*n.storms)/1e6 popstorms_m from n join hexcty h using (h3) group by 1""")
    res[t]=c.sql(f"select round(sum(pop_m)), list(a3 order by pop_m desc)[1:10] from {t}").fetchall()[0]
    print(t, res[t])
def ov(a,b): return len(set(res[a][1])&set(res[b][1]))
print('overlap usa1/wmo1',ov('e_usa_1','e_wmo_1'),'usa1/usa2',ov('e_usa_1','e_usa_2'))
print(c.sql("select a3, round(u.pop_m) usa, round(w.pop_m) wmo from e_usa_1 u full join e_wmo_1 w using (a3) order by greatest(coalesce(u.pop_m,0),coalesce(w.pop_m,0)) desc limit 12").fetchall())

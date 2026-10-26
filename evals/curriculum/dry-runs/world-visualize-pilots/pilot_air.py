# Pilot F: population far from an open airport with a long paved runway, vs from any airport with scheduled service.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load h3')
print(c.sql("select upper(trim(surface)) s, count(*) from 'data/runways.parquet' group by 1 order by 2 desc limit 25").fetchall())
print(c.sql("select count(distinct upper(trim(surface))), count(*) filter (where closed::varchar in ('1','true')), count(length_ft) from 'data/runways.parquet'").fetchall())
c.sql("""create or replace table rw as select airport_ident, length_ft, upper(trim(surface)) s, closed::varchar closed from 'data/runways.parquet'""")
c.sql("""create or replace table ap as select a.ident, a.type, a.scheduled_service, a.iso_country, h3_latlng_to_cell_string(a.latitude_deg, a.longitude_deg, 4) cell,
  max(case when regexp_matches(r.s, '^(ASP|CON|PEM|BIT|TAR|PAV|ASPH|CONC)') and r.closed not in ('1','true') then r.length_ft end) paved_len
  from 'data/airports.parquet' a left join rw r on r.airport_ident=a.ident where a.type not in ('closed','heliport','seaplane_base','balloonport') group by all""")
for name,cond in (('sched',"scheduled_service='yes'"),('paved6000','paved_len>=6000'),('paved8000','paved_len>=8000')):
    print(name, c.sql(f"select count(*) from ap where {cond}").fetchall())
    for k in (3,5):
        c.sql(f"create or replace table r_{name}_{k} as select distinct unnest(h3_grid_disk(cell,{k})) h3 from ap where {cond}")
        print(' k',k, c.sql(f"select round(sum(pop) filter (where h3 not in (select h3 from r_{name}_{k}))/1e6) far_m from hexcty").fetchall())
print(c.sql("""select a3, round(sum(pop)/1e6) pop_m, round(sum(pop) filter (where h3 not in (select h3 from r_paved6000_5))/sum(pop),2) far_paved,
  round(sum(pop) filter (where h3 not in (select h3 from r_sched_5))/sum(pop),2) far_sched from hexcty group by 1 having sum(pop)>1e7 order by far_paved desc limit 10""").fetchall())

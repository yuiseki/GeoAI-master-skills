# Pilot H2: refugee-weighted distance between origin and asylum country (border-to-border and centroid), by year.
import duckdb
c=duckdb.connect('pilot.duckdb'); c.sql('load spatial'); c.sql('set geometry_always_xy=true')
c.sql("""create or replace table rfa as select Year y, "Country of origin (ISO)" o, "Country of asylum (ISO)" a, "Refugees under UNHCR's mandate" r from 'data/unhcr.parquet' where "Refugees under UNHCR's mandate">0 and Year>=1990""")
c.sql("create or replace table pairs as select distinct o, a from rfa")
c.sql("""create or replace table pd as select p.o, p.a, ST_Distance_Sphere(ST_PointOnSurface(x.g), ST_PointOnSurface(y.g))/1000 cdist,
   exists (select 1 from nb where nb.x=p.o and nb.y=p.a) adj from pairs p join ne x on x.iso3=p.o join ne y on y.iso3=p.a""")
print(c.sql("select count(*) pairs, (select count(*) from pairs) all_pairs from pd").fetchall())
print(c.sql("""select y, round(sum(r)/1e6,1) r_m, round(sum(r) filter (where adj)/sum(r),2) adj_share,
  round(quantile_cont(cdist, 0.5) filter (where true),0) med_pair_km, round(sum(r*cdist)/sum(r)) mean_km_weighted,
  round(sum(r) filter (where pd.o is null)/sum(r),3) unmatched from rfa left join pd using (o,a) where y in (1990,1995,2000,2005,2010,2015,2020,2022,2025) group by 1 order by 1""").fetchall())
print('2025 weighted mean distance excluding top origin', c.sql("select o, round(sum(r)/1e6,2) from rfa where y=2025 group by 1 order by 2 desc limit 6").fetchall())

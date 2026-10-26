# Pilot E: legal clock minus mean solar time at each populated H3 r4 cell, population-weighted.
import duckdb, datetime
from zoneinfo import ZoneInfo
import tzdata
c=duckdb.connect('pilot.duckdb'); c.sql('load spatial'); c.sql('set geometry_always_xy=true')
print('tzdata', tzdata.IANA_VERSION)
c.sql("create or replace table tzp as select tzid, ST_SetCRS(geometry,'OGC:CRS84') g from 'data/tz.parquet'")
c.sql("create or replace table hextz as select h.h3, h.pop, h.a3, ST_X(h.ctr) lon, t.tzid from hexcty h left join tzp t on ST_Intersects(t.g, h.ctr)")
print(c.sql("select count(*), count(distinct h3), count(*) filter (where tzid is null), round(sum(pop) filter (where tzid is null)/1e6) from hextz").fetchall())
rows=[]
for (tz,) in c.sql("select distinct tzid from hextz where tzid is not null").fetchall():
    z=ZoneInfo(tz)
    jan=datetime.datetime(2025,1,15,12,tzinfo=datetime.timezone.utc).astimezone(z).utcoffset().total_seconds()/3600
    jul=datetime.datetime(2025,7,15,12,tzinfo=datetime.timezone.utc).astimezone(z).utcoffset().total_seconds()/3600
    rows.append((tz,jan,jul))
c.sql("create or replace table tzoff(tzid varchar, jan double, jul double)"); c.executemany("insert into tzoff values (?,?,?)", rows)
c.sql("create or replace table dev as select h.*, o.jan - lon/15 dev_jan, o.jul - lon/15 dev_jul from hextz h join tzoff o using (tzid)")
print(c.sql("select round(sum(pop*abs(dev_jan))/sum(pop),2) mean_abs_jan, round(sum(pop*abs(dev_jul))/sum(pop),2) jul, round(sum(pop) filter (where dev_jan>=1)/1e6) ahead1h_jan_m, round(sum(pop) filter (where dev_jul>=1)/1e6) ahead1h_jul_m, round(sum(pop) filter (where dev_jan>=2)/1e6) ahead2h_m from dev").fetchall())
print('largest pop-weighted deviation by country (jan)', c.sql("select a3, round(sum(pop)/1e6) pop_m, round(sum(pop*dev_jan)/sum(pop),2) d, round(max(dev_jan)-min(dev_jan),2) spread from dev group by 1 having sum(pop)>5e6 order by abs(sum(pop*dev_jan)/sum(pop)) desc limit 10").fetchall())
print('centroid-of-zone vs population weighting', c.sql("select tzid, round(avg(dev_jan),2) area_mean, round(sum(pop*dev_jan)/sum(pop),2) pop_mean, round(sum(pop)/1e6) pop_m from dev group by 1 having sum(pop)>2e7 order by abs(avg(dev_jan)-sum(pop*dev_jan)/sum(pop)) desc limit 8").fetchall())

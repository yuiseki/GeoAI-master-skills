copy (
  with d as (
    select country_code, indicator_code, value
    from 'hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/data.parquet'
    where year = 2022 and indicator_code in
      ('SP.DYN.LE00.IN', 'NY.GDP.PCAP.CD', 'SP.POP.TOTL', 'SP.URB.TOTL.IN.ZS')
  ), c as (
    select "Country Code" as iso3, "Region" as region
    from 'hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/countries.parquet'
    where "Region" <> ''
  )
  select c.iso3, c.region,
    max(value) filter (where indicator_code = 'SP.DYN.LE00.IN') as life_exp,
    ln(max(value) filter (where indicator_code = 'NY.GDP.PCAP.CD')) as log_gdp_pc,
    ln(max(value) filter (where indicator_code = 'SP.POP.TOTL')) as log_pop,
    max(value) filter (where indicator_code = 'SP.URB.TOTL.IN.ZS') as urban_pct
  from c left join d on d.country_code = c.iso3
  group by all order by iso3
) to 'tmp/wdi_2022.parquet' (format parquet);
select count(*) as countries, count(life_exp) as with_life, count(log_gdp_pc) as with_gdp,
       count(log_pop) as with_pop, count(urban_pct) as with_urban,
       count(*) filter (where life_exp is not null and log_gdp_pc is not null and log_pop is not null and urban_pct is not null) as complete
from 'tmp/wdi_2022.parquet';

"""How many designated emergency evacuation sites each of Tokyo's 23 wards registered, by hazard.

uvx --from 'duckdb>=1.5.5' python scripts/00_site_registration.py

Writes outputs/site_registration_tokyo23.csv. A ward with 0 rows has no registration in the frozen table: that
is "not registered", not "no site".
"""
from pathlib import Path

import duckdb

OUT = Path(__file__).resolve().parent.parent / "outputs"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
SITES = "hf://datasets/yuiseki/gsi-evacuation-sites-jp@d8ad2169789b71c951e8808b2e54a953030aae07/parquet/sites.parquet"

c = duckdb.connect()
c.execute("install httpfs; load httpfs")
c.execute(f"""copy (
  select m.code5, m.name, coalesce(s.n, 0) sites, coalesce(s.earthquake, 0) earthquake, coalesce(s.flood, 0) flood,
         coalesce(s.large_fire, 0) large_fire, coalesce(s.inland_flooding, 0) inland_flooding
  from (select code5, name from '{ADMIN}' where code5 between '13101' and '13123') m
  left join (select substr(common_id, 2, 5) code5, count(*) n, sum(earthquake::int) earthquake, sum(flood::int) flood,
                    sum(large_fire::int) large_fire, sum(inland_flooding::int) inland_flooding
             from '{SITES}' group by 1) s using (code5)
  order by m.code5) to '{OUT / "site_registration_tokyo23.csv"}' (header, delimiter ',')""")
print(open(OUT / "site_registration_tokyo23.csv", encoding="utf-8").read())

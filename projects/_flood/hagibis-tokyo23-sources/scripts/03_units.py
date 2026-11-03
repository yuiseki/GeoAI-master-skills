"""The 23 wards as polygons with the 床上浸水 count of the Tokyo report of 2019-11-08 14:00, for classify_map.py.

uvx --with duckdb==1.5.5 python scripts/03_units.py

Reads the N03 GeoJSON (国土数値情報 行政区域, 2026-01-01, JGD2011) inside the local tree of ksj-a31a-flood-greater-tokyo,
dissolves the 23 wards (N03_007 13101 to 13123) and projects them to JGD2011 plane rectangular IX (EPSG:6677). Writes
artifacts/_flood/hagibis-tokyo23-sources/wards23.parquet with: code, name, 床上浸水 (the count in the report; 0
for a ward that has a row with a blank 床上 cell; null for a ward with no row in the report, drawn as NoData), and
outputs/wards23_values.csv with the same values.
"""
import csv
import json
import re
import tempfile
import zipfile
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/hagibis-tokyo23-sources"
N03 = Path("/sata_hdd_24tb/hf_data/ksj-a31a-flood-greater-tokyo/data/docs/N03-20260101_13_GML.zip")


def main():
    vals = {}
    with open(HERE.parent / "outputs/tokyo_sources.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["as_of"] == "2019-11-08 14:00" and r["topic"] == "damage":
                if r["fact"] == "表に行が無い":
                    vals[r["ward"]] = None
                else:
                    m = re.search(r"浸水 \(床上\) (\d+)", r["fact"])
                    vals[r["ward"]] = int(m.group(1)) if m else 0
    if len(vals) != 23:
        raise RuntimeError(f"expected 23 wards, got {len(vals)}")
    tmpdir = tempfile.TemporaryDirectory()  # the system temp, not the working tree
    tmp = Path(tmpdir.name) / "n03_13.geojson"
    with zipfile.ZipFile(N03) as z:
        tmp.write_bytes(z.read("N03-20260101_13.geojson"))
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial")
    c.sql(f"""create table w as select N03_007 as code, N03_004 as name,
              ST_Transform(ST_Union_Agg(geom), 'EPSG:6668', 'EPSG:6677', always_xy := true) as geometry
              from ST_Read('{tmp}') where N03_007 between '13101' and '13123' group by all""")
    c.sql('create table v (name varchar, "床上浸水" integer)')
    c.executemany("insert into v values (?, ?)", list(vals.items()))
    n = c.sql("select count(*) from w join v using (name)").fetchone()[0]
    if n != 23:
        raise RuntimeError(f"joined {n} of 23 wards")
    c.sql(f"""copy (select code, name, "床上浸水", geometry from w join v using (name) order by code)
              to '{ART / "wards23.parquet"}' (format parquet)""")
    rows = c.sql('select code, name, "床上浸水" from w join v using (name) order by code').fetchall()
    with open(HERE.parent / "outputs/wards23_values.csv", "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["code", "name", "above_floor_20191108"])
        wr.writerows([[a, b, "" if v is None else v] for a, b, v in rows])
    tmpdir.cleanup()
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()

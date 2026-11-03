"""The 2019 polygons of the Tokyo flood records (tokyo-flood-record-jp) in the 23 wards, next to the damage counts
that the Tokyo Metropolitan Government reported for the same wards (outputs/tokyo_sources.csv, 2019-11-08 14:00).

uvx --with duckdb==1.5.5 python scripts/01_record_vs_reports.py

Writes outputs/record_vs_reports.csv: per ward, the number of record polygons, the distinct (district, area) pairs
(one record is split into several identical polygons), the record's 床上 and 床下 building counts as written (text,
with the source's parentheses), and the reported 床上 and 床下 counts.
"""
import csv
import re
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
REC = "/sata_hdd_24tb/hf_data/tokyo-flood-record-jp/data/parquet/flood_area.parquet"  # local tree, commit 4c88d8d
WARDS = ["千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区", "江東区", "品川区", "目黒区", "大田区", "世田谷区",
         "渋谷区", "中野区", "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区", "葛飾区", "江戸川区"]


def main():
    c = duckdb.connect()
    rows = c.sql(f"select munic, district, area, otf_bldg, utf_bldg from '{REC}' where year = 2019").fetchall()
    rep = {}
    with open(HERE.parent / "outputs/tokyo_sources.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["as_of"] == "2019-11-08 14:00" and r["topic"] == "damage":
                up = re.search(r"浸水 \(床上\) (\d+)", r["fact"])
                dn = re.search(r"浸水 \(床下\) (\d+)", r["fact"])
                rep[r["ward"]] = (up.group(1) if up else "", dn.group(1) if dn else "")
    out = []
    for w in WARDS:
        mine = [r for r in rows if r[0] == w]
        uniq = sorted({(r[1], r[2], r[3], r[4]) for r in mine})
        out.append({"ward": w, "record_polygons": len(mine), "record_distinct": len(uniq),
                    "record_districts": "、".join(u[0] for u in uniq),
                    "record_above_floor_bldg": " / ".join(u[2] for u in uniq),
                    "record_below_floor_bldg": " / ".join(u[3] for u in uniq),
                    "reported_above_floor_20191108": rep.get(w, ("", ""))[0],
                    "reported_below_floor_20191108": rep.get(w, ("", ""))[1]})
    with open(HERE.parent / "outputs/record_vs_reports.csv", "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)
    for o in out:
        if o["record_polygons"] or o["reported_above_floor_20191108"] or o["reported_below_floor_20191108"]:
            print(o)


if __name__ == "__main__":
    main()

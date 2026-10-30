"""Counts the report quotes that no other step writes: the records of the 23 wards by cause, and the test cells of
figure 3 by ward.

uvx --from 'duckdb>=1.5.5' python scripts/12_summary.py

Writes outputs/summary.json and outputs/test_cells_by_ward.csv. A record is a polygon of tokyo-flood-record-jp that
touches a ward (JGD2000 read as JGD2011, as in 02_grid.py). Its cause is "内水" when `reason` mentions 内水 and not
溢水 (内水　窪地浸水 counts as 内水), "溢水" the other way round (有堤部溢水 counts), "両方" when it mentions both, and
"その他" when it mentions neither.
"""
import json
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a"
OUT = HERE.parent / "outputs"


def main():
    c = duckdb.connect()
    c.execute("load spatial")
    c.execute(f"create table w as select name, geometry from '{ART / 'raw/wards.parquet'}'")
    c.execute(f"""create table r as select distinct f.year, f.layer, f.row, regexp_replace(coalesce(f.reason, ''), '[\\s　]', '', 'g') reason
        from '{ART / 'raw/flood_record_area.parquet'}' f join w on st_intersects(f.geometry, w.geometry)""")
    cause = c.execute("""select case when reason like '%内水%' and reason like '%溢水%' then '両方'
            when reason like '%内水%' then '内水' when reason like '%溢水%' then '溢水' else 'その他' end k, count(*) from r group by 1 order by 2 desc""").fetchall()
    total = sum(n for _, n in cause)
    c.execute(f"create table s as select * from '{ART / 'maps/cells_sq.parquet'}' where test_cat is not null")
    wards = c.execute("""select w.name, count(*) filter (where test_cat = 1), count(*) filter (where test_cat = 2),
            count(*) filter (where test_cat = 3), count(*) filter (where test_cat = 4), count(*)
        from s join w on st_contains(w.geometry, st_transform(st_point(s.x, s.y), 'EPSG:6677', 'EPSG:6668', always_xy := true))
        group by 1 order by 3 desc, 1""").fetchall()
    with open(OUT / "test_cells_by_ward.csv", "w") as f:
        f.write("ward,both,model_only,a31a_only,neither,total\n")
        for row in wards:
            f.write(",".join(map(str, row)) + "\n")
    res = {"records_in_wards": total, "records_by_cause": dict(cause),
           "share_naisui_only": round(dict(cause).get("内水", 0) / total, 4),
           "test_cells_located": sum(row[5] for row in wards)}
    (OUT / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(res, ensure_ascii=False))
    for row in wards[:6]:
        print(row)


if __name__ == "__main__":
    main()

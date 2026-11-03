"""Draw the 23 wards on maps with the skill's classify_map.py: the share of accidents with a cyclist, and the change
from 2019 to 2025, the five central wards outlined (the k=2 group, when it passed the rule of C5).

Run from the repository root after analyze.py and clusters.py:
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib \
  python projects/_traffic_accident/tokyo23-ward-comparison/scripts/maps.py
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
ART = ROOT / "artifacts/_traffic_accident" / PROJECT.name
OUT = PROJECT / "outputs"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/classify_map.py"
SOURCE = "警察庁 交通事故オープンデータ 2019-2025 (npa-traffic-accidents@389500a)、行政界 (jp-admin-2026-09@e6c87b1)"
# (column, png name, kind, unit, classification arguments, title)
MAPS = [
    ("自転車の割合", "map-bike", "rate", "%", ["--method", "quantile", "--classes", "5"],
     "23区の人身事故のうち、自転車が関わる割合 (2019〜2025年、太枠は都心の5区の群)"),
    ("件数の比", "map-trend", "change", "2025年 / 2019年",
     ["--method", "fixed", "--thresholds", "0.8", "0.9", "1.0", "1.1", "1.2", "1.3", "--centre", "1.0"],
     "23区の人身事故の件数は2019年から2025年にどれだけ変わったか (太枠は都心の5区の群)"),
]


def main():
    with (OUT / "wards.csv").open(encoding="utf-8") as f:
        wards = {r["code"]: r for r in csv.DictReader(f)}
    con = duckdb.connect()
    con.sql("install spatial; load spatial")
    con.sql("create table v (code5 varchar, share_bike double, ratio_2025_2019 double)")
    con.executemany("insert into v values (?, ?, ?)", [("13" + c, 100 * float(w["share_bike"]), float(w["ratio_2025_2019"]))
                                                       for c, w in wards.items()])
    table = ART / "ward_values.parquet"
    # Japanese column names: classify_map writes the value column's name in the legend.
    con.sql(f"""copy (select w.code5, w.name, v.share_bike as "自転車の割合", v.ratio_2025_2019 as "件数の比",
        ST_GeomFromWKB(w.geometry) as geometry from '{ART / 'wards.parquet'}' w
        join v using (code5) order by code5) to '{table}' (format parquet)""")
    highlight = PROJECT / "tmp/central-five.csv"
    highlight.parent.mkdir(exist_ok=True)
    groups = []
    if (OUT / "clusters.csv").exists():
        with (OUT / "clusters.csv").open(encoding="utf-8") as f:
            groups = [r for r in csv.DictReader(f) if r["k"] == "2"]
    central = sorted({r["group"] for r in groups if r["name"] == "千代田区"})
    with highlight.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "group"])
        writer.writerows(["13" + r["code"], "都心の5区の群"] for r in groups if r["group"] in central)
    record = {}
    for col, name, kind, unit, how, title in MAPS:
        png = OUT / f"{name}.png"
        subprocess.run([sys.executable, str(DRAW), str(table), "code5", col, "--kind", kind, "--unit", unit, *how,
                        "--crs", "EPSG:4612", "--source", SOURCE, "--label", "name", "--title", title,
                        "--highlight", str(highlight), "--expect-units", "23", "--png", str(png)], check=True)
        meta = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
        record[name] = {k: meta.get(k) for k in ("breaks", "units_per_class", "text_overlaps", "class_change_share")}
    print(json.dumps(record, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

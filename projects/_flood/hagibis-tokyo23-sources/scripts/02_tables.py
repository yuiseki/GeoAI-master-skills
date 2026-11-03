"""Small tables for the figures, transcribed by hand from the sources (the values are as the sources write them).

python3 scripts/02_tables.py

- outputs/damage_versions.csv: 床上 and 床下 浸水 of 世田谷区 and 大田区 in each version of the Tokyo damage reports
  (棟 as the tables count them), with the local PDF. The 10-16 report counts 件 in its text and is kept with its unit.
- outputs/evacuation_compare.csv: per ward, the evacuees in the Tokyo table at 2019-10-13 05:00 and, where a ward (or
  MLIT) document gives one, the largest number it reports, with the row of ward_sources.csv it comes from.
Every damage value was checked against the PDF text (column checked_against_pdf).
"""
import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs"
DOCS = "artifacts/_flood/hagibis-tokyo23-sources/raw/docs/"

DAMAGE = [  # ward, as_of, above, below, unit, file, checked_against_pdf
    ("世田谷区", "2019-10-15 12:00", 156, 2, "棟", "tokyo_honbu2_2019101502.pdf", "yes"),
    ("大田区", "2019-10-15 12:00", 11, 4, "棟", "tokyo_honbu2_2019101502.pdf", "yes"),
    ("世田谷区", "2019-10-16 12:00", 136, 12, "件", "tokyo_higai_20191016.pdf", "yes"),
    ("大田区", "2019-10-16 12:00", 583, 7, "件", "tokyo_higai_20191016.pdf", "yes"),
    ("世田谷区", "2019-10-18 14:00", 295, 26, "棟", "tokyo_higai_20191018.pdf", "yes"),
    ("大田区", "2019-10-18 14:00", 583, 7, "棟", "tokyo_higai_20191018.pdf", "yes"),
    ("世田谷区", "2019-10-23 14:00", 324, 35, "棟", "tokyo_higai_20191023.pdf", "yes"),
    ("大田区", "2019-10-23 14:00", 373, 209, "棟", "tokyo_higai_20191023.pdf", "yes"),
    ("世田谷区", "2019-10-25 14:00", 334, 37, "棟", "tokyo_higai_20191025.pdf", "yes"),
    ("大田区", "2019-10-25 14:00", 373, 209, "棟", "tokyo_higai_20191025.pdf", "yes"),
    ("世田谷区", "2019-11-05 18:00", 372, 43, "棟", "tokyo_higai_2019110602.pdf", "yes"),
    ("大田区", "2019-11-05 18:00", 203, 267, "棟", "tokyo_higai_2019110602.pdf", "yes"),
    ("世田谷区", "2019-11-08 14:00", 372, 42, "棟", "tokyo_higai_191108.pdf", "yes"),
    ("大田区", "2019-11-08 14:00", 203, 267, "棟", "tokyo_higai_191108.pdf", "yes"),
]

# Tokyo table at 2019-10-13 05:00 (tokyo_sources.csv, read from the page image); None where the cell is blank
TOKYO_0500 = {"千代田区": 39, "中央区": 56, "港区": 0, "新宿区": 293, "文京区": 328, "台東区": 50, "墨田区": None,
              "江東区": 5153, "品川区": 272, "目黒区": 426, "大田区": 6724, "世田谷区": 0, "渋谷区": 0, "中野区": 270,
              "杉並区": 844, "豊島区": None, "北区": 2108, "荒川区": 0, "板橋区": 0, "練馬区": 593, "足立区": 0,
              "葛飾区": 19638, "江戸川区": 21919}
# the largest number a ward (or MLIT) document gives: (value, what it is, ward_sources.csv line, source_type)
PEAK = {"世田谷区": (5376, "最大", 100, "ward"), "大田区": (11791, "最大 (国交省の資料、都の検証資料から引用)", 113, "mlit"),
        "江戸川区": (35040, "最大", 115, "ward"), "葛飾区": (19823, "総数", 122, "ward"),
        "足立区": (33172, "計 (ピークは 12 日 22 時ごろ)", 124, "other_official"), "練馬区": (629, "ピーク時", 128, "ward"),
        "板橋区": (1529, "12 日 21 時", 133, "ward"), "品川区": (584, "最大 (22 時)", 135, "ward")}


def main():
    with open(OUT / "damage_versions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ward", "as_of", "above_floor", "below_floor", "unit", "local_file", "checked_against_pdf"])
        for r in DAMAGE:
            w.writerow(list(r[:5]) + [DOCS + r[5], r[6]])
    with open(OUT / "evacuation_compare.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ward", "tokyo_20191013_0500", "ward_doc_value", "ward_doc_kind", "ward_sources_line", "source_type"])
        for ward, v in TOKYO_0500.items():
            p = PEAK.get(ward)
            w.writerow([ward, "" if v is None else v] + (list(p) if p else ["", "", "", ""]))
    print("ok")


if __name__ == "__main__":
    main()

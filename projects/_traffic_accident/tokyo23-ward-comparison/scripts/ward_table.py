"""Rewrite the table of the wards in report.md (between the two marker comments) from outputs/profiles.csv, with a
link to each ward's own report where it exists, so that the table never drifts from the outputs.

Run from the repository root after summarize.py:
python3 projects/_traffic_accident/tokyo23-ward-comparison/scripts/ward_table.py
"""

import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPORT = PROJECT / "report.md"
START, END = "<!-- ward-table -->", "<!-- /ward-table -->"
SLUG = {"101": "chiyoda", "102": "chuo", "103": "minato", "104": "shinjuku", "105": "bunkyo", "106": "taito",
        "107": "sumida", "108": "koto", "109": "shinagawa", "110": "meguro", "111": "ota", "112": "setagaya",
        "113": "shibuya", "114": "nakano", "115": "suginami", "116": "toshima", "117": "kita", "118": "arakawa",
        "119": "itabashi", "120": "nerima", "121": "adachi", "122": "katsushika", "123": "edogawa"}


def rows(profiles, exists):
    out = ["| 区 | 高い | 低い | 量の順位 | 2025 年 / 2019 年 | 自転車の単独を除く | 区ごとの報告 |",
           "|---|---|---|---|---|---|---|"]
    for r in profiles:
        slug = SLUG[r["code"]]
        link = f"[{slug}](../{slug}-accident-trends-by-role/report.md)" if exists(slug) else "作成中"
        out.append(f"| {r['name']} | {r['high'] or 'なし'} | {r['low'] or 'なし'} | "
                   f"{r['rank_per_1000']}、{r['rank_per_road_km']}、{r['rank_per_km2']} | "
                   f"{r['trend_2025']} ({r['ratio_2025_2019']}) | {r['trend_2025_without_bike_alone']} | {link} |")
    return out


def main():
    with (PROJECT / "outputs/profiles.csv").open(encoding="utf-8") as f:
        profiles = list(csv.DictReader(f))
    exists = lambda slug: (PROJECT.parent / f"{slug}-accident-trends-by-role/report.md").exists()
    text = REPORT.read_text(encoding="utf-8")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    REPORT.write_text(head + START + "\n" + "\n".join(rows(profiles, exists)) + "\n" + END + tail, encoding="utf-8")
    print(sum(exists(SLUG[r["code"]]) for r in profiles), "of", len(profiles), "wards linked")


if __name__ == "__main__":
    main()

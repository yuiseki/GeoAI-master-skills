"""Print the derived counts quoted in the reports (from outputs/*.csv) into outputs/summary.txt.

Run from the repository root after analyze.py and plot.py (it reads plot.py's school-map.json):
python3 projects/_traffic_accident/nerima-accident-trends-by-role/scripts/summarize.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "outputs"
SLUG = PROJECT.name.removesuffix("-accident-trends-by-role")


def rows(name):
    with (OUT / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    # The ward's name is the scope of yearly.csv that is not the 23 wards (analyze.WARD_NAME; this script runs
    # without duckdb, so it does not import analyze).
    ward_name = next(r["scope"] for r in rows("yearly.csv") if r["scope"] != "23区")
    lines = []
    deaths = rows("deaths.csv")
    lines.append(f"deaths accidents {len(deaths)}; dead party {dict(Counter(r['dead_party'] for r in deaths))}; "
                 f"party A {dict(Counter(r['type_A'] for r in deaths))}")
    lines.append(f"deaths hour 0-5 {sum(int(r['hour']) <= 5 for r in deaths)}; "
                 f"hour 19-5 {sum(int(r['hour']) >= 19 or int(r['hour']) <= 5 for r in deaths)}")
    ages = [r["age_A"] if r["type_A"] == "歩行者" else r["age_B"] for r in deaths if r["dead_party"] == "歩行者"]
    lines.append(f"dead pedestrians aged 65+ {sum(a in ('65', '75') for a in ages)} of {len(ages)}")
    hours = rows("hour_weekday.csv")
    for group in ("全て", "若い歩行者・自転車", "高齢の歩行者", "自転車"):
        every, weekday = Counter(), Counter()
        for r in hours:
            if r["group"] == group:
                every[int(r["hour"])] += int(r["accidents"])
                if 2 <= int(r["weekday"]) <= 6:
                    weekday[int(r["hour"])] += int(r["accidents"])
        lines.append(f"{group}: n {sum(every.values())}; top hours {every.most_common(4)}; "
                     f"weekday (Mon-Fri) n {sum(weekday.values())}; weekday top hours {weekday.most_common(4)}")
    parties = rows("party_matrix.csv")
    for kind in ("乗用車 (自家用)", "乗用車 (事業用)", "貨物車", "自転車", "二輪車"):
        a = sum(int(r["accidents"]) for r in parties if r["party_A"] == kind)
        b = sum(int(r["accidents"]) for r in parties if r["party_B"] == kind)
        lines.append(f"{kind}: as party A {a}; as party B {b}")
    cars = ("乗用車 (自家用)", "乗用車 (事業用)", "貨物車")
    lines.append(f"bike as B with a car or truck as A {sum(int(r['accidents']) for r in parties if r['party_B'] == '自転車' and r['party_A'] in cars)}")
    towns = rows("towns.csv")
    lines.append(f"towns: accidents in towns {sum(int(r['accidents']) for r in towns)}; most accidents "
                 f"{[(r['name'], r['accidents'], r['ped']) for r in sorted(towns, key=lambda r: -int(r['accidents']))[:8]]}")
    yearly = [r for r in rows("yearly.csv") if r["scope"] == ward_name]
    lines.append(f"{SLUG} 7 years: accidents {sum(int(r['accidents']) for r in yearly)}; died {sum(int(r['died']) for r in yearly)}; "
                 f"hurt {sum(int(r['hurt']) for r in yearly)}")
    mine = next(r for r in rows("wards.csv") if r["name"] == ward_name)
    lines.append(f"{SLUG} shares (%): " + "; ".join(f"{k} {100 * float(v):.1f}" for k, v in mine.items() if k.startswith("share_")))
    school_map = json.loads((OUT / "school-map.json").read_text(encoding="utf-8"))
    lines.append(f"school map: young pedestrians and cyclists {school_map['n']}")
    lines.append(f"party cells: " + "; ".join(f"{r['party_A']} x {r['party_B']} {r['accidents']}" for r in parties[:12]))
    # Route classes over the 7 years (route_class.csv is by year), and the routes and roads of the top 15 hotspots
    # (Katsushika added both after its first run; they are part of the template now).
    routes = Counter()
    for r in rows("route_class.csv"):
        routes[r["route_class"]] += int(r["accidents"])
    lines.append("route classes 7 years: " + "; ".join(f"{k} {v}" for k, v in routes.most_common()))
    hot = rows("hotspots.csv")
    lines.append("top 15 hotspots: top route " + str(dict(Counter(h["top_route"] for h in hot).most_common()))
                 + "; road_1 " + str(dict(Counter(h["road_1"] or "(none within 30 m)" for h in hot).most_common()))
                 + f"; with 首都高速 accidents {sum(int(h['expressway']) > 0 for h in hot)}")
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

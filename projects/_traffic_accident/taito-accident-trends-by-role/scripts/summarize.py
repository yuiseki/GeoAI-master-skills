"""Print the derived counts quoted in the reports (from outputs/*.csv) into outputs/summary.txt.

Run from the repository root after analyze.py:
python3 projects/_traffic_accident/taito-accident-trends-by-role/scripts/summarize.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"


def rows(name):
    with (OUT / name).open() as f:
        return list(csv.DictReader(f))


def main():
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
    yearly = [r for r in rows("yearly.csv") if r["scope"] == "台東区"]
    lines.append(f"taito 7 years: accidents {sum(int(r['accidents']) for r in yearly)}; died {sum(int(r['died']) for r in yearly)}; "
                 f"hurt {sum(int(r['hurt']) for r in yearly)}")
    taito = next(r for r in rows("wards.csv") if r["name"] == "台東区")
    lines.append("taito shares (%): " + "; ".join(f"{k} {100 * float(v):.1f}" for k, v in taito.items() if k.startswith("share_")))
    school_map = json.loads((OUT / "school-map.json").read_text())
    lines.append(f"school map: young pedestrians and cyclists {school_map['n']}")
    lines.append(f"party cells: " + "; ".join(f"{r['party_A']} x {r['party_B']} {r['accidents']}" for r in parties[:12]))
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

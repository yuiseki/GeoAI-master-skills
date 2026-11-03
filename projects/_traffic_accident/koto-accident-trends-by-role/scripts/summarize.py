"""Print the derived counts quoted in the reports (from outputs/*.csv) into outputs/summary.txt.

Run from the repository root after analyze.py:
python3 projects/_traffic_accident/koto-accident-trends-by-role/scripts/summarize.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"


def rows(name):
    with (OUT / name).open(encoding="utf-8") as f:
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
    yearly = [r for r in rows("yearly.csv") if r["scope"] == "江東区"]
    lines.append(f"koto 7 years: accidents {sum(int(r['accidents']) for r in yearly)}; died {sum(int(r['died']) for r in yearly)}; "
                 f"hurt {sum(int(r['hurt']) for r in yearly)}")
    koto = next(r for r in rows("wards.csv") if r["name"] == "江東区")
    lines.append("koto shares (%): " + "; ".join(f"{k} {100 * float(v):.1f}" for k, v in koto.items() if k.startswith("share_")))
    school_map = json.loads((OUT / "school-map.json").read_text(encoding="utf-8"))
    lines.append(f"school map: young pedestrians and cyclists {school_map['n']}")
    lines.append(f"party cells: " + "; ".join(f"{r['party_A']} x {r['party_B']} {r['accidents']}" for r in parties[:12]))
    # Added for Koto (after the first run): the single-vehicle deaths, the bicycle-alone share, and the hotspots that
    # rose from the first to the second half.
    lines.append(f"deaths by kind (01 人対車両, 21 車両相互, 41 車両単独) x dead party "
                 f"{dict(Counter(r['kind'] + ' ' + r['dead_party'] for r in deaths))}")
    alone = sum(int(r["accidents"]) for r in parties if r["party_A"] == "自転車" and r["party_B"] == "相手なし・物件")
    lines.append(f"bike alone (A 自転車, B 相手なし・物件) {alone}; share of all {100 * alone / sum(int(r['accidents']) for r in yearly):.1f}%")
    hot = rows("hotspots.csv")
    lines.append(f"hotspots top {len(hot)}: second half per year above first {sum(float(h['second_per_year']) > float(h['first_per_year']) for h in hot)}; "
                 f"below {sum(float(h['second_per_year']) < float(h['first_per_year']) for h in hot)}; "
                 f"both halves with accidents {sum(int(h['first_2019_2021']) > 0 and int(h['second_2022_2025']) > 0 for h in hot)}")
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

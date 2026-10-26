"""Summarize saved mesh-level results without re-reading source datasets.

uv run --no-project python3 projects/japan-bus-operator-concentration-replication/scripts/diagnostics.py
"""

import csv
import json
from collections import defaultdict

from analysis import ARTIFACTS, PROJECT


def top_overlap(a, b, k):
    top_a = {code for code, _ in sorted(a.items(), key=lambda item: (-item[1], item[0]))[:k]}
    top_b = {code for code, _ in sorted(b.items(), key=lambda item: (-item[1], item[0]))[:k]}
    return len(top_a & top_b)


def summarize_municipalities(rows):
    rows = list(rows)
    eligible = [r for r in rows if int(r["stop_older_population"]) >= 10000]
    fully_single = [r for r in eligible if int(r["stop_older_population"]) == int(r["single_older_population"])]
    fully_single.sort(key=lambda r: (-int(r["single_older_population"]), r["code5"]))
    top_scale = sorted(rows, key=lambda r: (-int(r["single_older_population"]), r["code5"]))[:20]
    return {
        "municipalities": len(rows),
        "with_stop_population": sum(int(r["stop_older_population"]) > 0 for r in rows),
        "share_100pct_with_denominator_10000": len(fully_single),
        "largest_100pct": [{"code5": r["code5"], "name": r["name"], "older_people": int(r["single_older_population"])} for r in fully_single[:5]],
        "top_20_by_single_population": [{"code5": r["code5"], "name": r["name"], "older_people": int(r["single_older_population"])} for r in top_scale],
    }


def main():
    with (PROJECT / "outputs/municipalities.csv").open(encoding="utf-8", newline="") as stream:
        municipalities = list(csv.DictReader(stream))
    audit = summarize_municipalities(municipalities)
    sums = {r: defaultdict(int) for r in (500, 800, 1000)}
    distributions = defaultdict(lambda: {"meshes": 0, "older_people": 0})
    with (ARTIFACTS / "meshes.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row["age65"] or int(row["age65"]) <= 0:
                continue
            age = int(row["age65"])
            code = row["municipality_code"]
            for r in sums:
                if int(row[f"operators_{r}m"]) == 1:
                    sums[r][code] += age
            n = int(row["operators_800m"])
            label = str(min(n, 4)) + ("+" if n >= 4 else "")
            distributions[label]["meshes"] += 1
            distributions[label]["older_people"] += age
    main_scale = {r["code5"]: int(r["single_older_population"]) for r in municipalities}
    if main_scale != dict(sums[800]):
        # Include 0-only municipalities in the comparison.
        if any(main_scale[k] != sums[800][k] for k in main_scale):
            raise ValueError("mesh and municipality sums disagree")
    audit["top20_overlap_vs_800m"] = {
        str(r): top_overlap(sums[800], sums[r], 20) for r in (500, 1000)
    }
    audit["operator_count_distribution_800m"] = dict(sorted(distributions.items()))
    (PROJECT / "outputs/diagnostics.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Write outputs/profiles.csv: for each ward, the features 1 sd or more above and below the 23 wards' mean, the
ranks on the three denominators, and the trend, as the material of the ward lines in report.md (C6).

Run from the repository root after analyze.py and clusters.py:
python3 projects/_traffic_accident/tokyo23-ward-comparison/scripts/summarize.py
"""

import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"
LABELS = {"share_ped": "歩行者", "share_bike": "自転車", "share_old_ped": "高齢の歩行者",
          "share_young_pb": "若い歩行者・自転車", "share_strict": "生活道路", "share_night": "夜",
          "share_intersection": "交差点", "share_bike_single": "自転車の単独", "share_business_car_A": "事業用の乗用車がA",
          "share_truck_A": "貨物車がA", "share_weekend": "土日", "share_expressway": "高速道路",
          "share_top15_hotspots": "上位15地点", "share_top10pct_towns": "上位10%の町丁"}


def notable(z, features, limit=1.0):
    """(above, below): 'label (z, share%)' for features with z >= limit and <= -limit, largest first."""
    above = sorted((f for f in features if float(z[f]) >= limit), key=lambda f: -float(z[f]))
    below = sorted((f for f in features if float(z[f]) <= -limit), key=lambda f: float(z[f]))
    return above, below


def main():
    with (OUT / "wards.csv").open(encoding="utf-8") as f:
        wards = {r["code"]: r for r in csv.DictReader(f)}
    with (OUT / "features_z.csv").open(encoding="utf-8") as f:
        zs = {r["code"]: r for r in csv.DictReader(f)}
    analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
    features = analysis["settings"]["features"] + ["share_top15_hotspots", "share_top10pct_towns"]
    ranks = analysis["audit"]["rank_of_rates"]
    pca = json.loads((OUT / "pca.json").read_text(encoding="utf-8"))["scores"]
    rows = []
    for code, w in wards.items():
        above, below = notable(zs[code], features)
        fmt = lambda fs: "、".join(f"{LABELS[f]} {100 * float(w[f]):.1f}% (z {float(zs[code][f]):+.2f})" for f in fs)
        rows.append({"code": code, "name": w["name"], "known_division": w["known_division"],
                     "high": fmt(above), "low": fmt(below),
                     "rank_per_1000": ranks["per_1000_residents_per_year"][code],
                     "rank_per_road_km": ranks["per_road_km_per_year"][code],
                     "rank_per_km2": ranks["per_km2_per_year"][code],
                     "ratio_2025_2019": w["ratio_2025_2019"], "trend_2025": w["trend_2025"],
                     "trend_2025_without_bike_alone": w["trend_2025_without_bike_alone"],
                     "pc1": pca[code][0], "pc2": pca[code][1]})
    with (OUT / "profiles.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(r["name"], "| 高:", r["high"], "| 低:", r["low"], "|", r["rank_per_1000"], r["rank_per_road_km"],
              r["rank_per_km2"], r["trend_2025"])


if __name__ == "__main__":
    main()

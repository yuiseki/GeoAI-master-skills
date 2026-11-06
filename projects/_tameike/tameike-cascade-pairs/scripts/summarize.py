"""One table of the three boxes from outputs/<box>_summary.json: outputs/summary.csv.

  python3 scripts/summarize.py
"""

import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs"
rows = []
for key in ("kagawa", "fukuyama", "awaji"):
    d = json.loads((OUT / f"{key}_summary.json").read_text(encoding="utf-8"))
    placed = d["assign_30m"]["hole"] + d["assign_30m"]["point"]
    rows.append(dict(
        box=key, ponds=d["n_ponds"], outside_grid=d["assign_30m"]["outside"],
        hole_30m=d["assign_30m"]["hole"], point_30m=d["assign_30m"]["point"],
        hole_share_30m_pct=round(100 * d["assign_30m"]["hole"] / placed, 1),
        hole_share_60m_pct=round(100 * d["assign_60m"]["hole"] / placed, 1),
        nodes=d["nodes"], nodes_2plus_ponds=d["nodes_with_2plus_ponds"],
        nodes_with_downstream=d["nodes_with_downstream_node"],
        nodes_with_downstream_pct=round(100 * d["nodes_with_downstream_node"] / d["nodes"], 1),
        top_only_5pct=d["top_only_in_cum_count"]["0.05"], top_only_10pct=d["top_only_in_cum_count"]["0.1"],
        top_only_20pct=d["top_only_in_cum_count"]["0.2"], top10_size=max(1, round(d["nodes"] * 0.10)),
        top_only_10pct_60m=d["top_only_in_cum_count_60m"]["0.1"],
        pairs_5m=d["pairs_5m"], pairs_10m=d["pairs_10m"], pairs_both=d["pairs_both"], jaccard_5m_10m=d["jaccard_5m_10m"],
        explore_top_only_10pct_within_500m=d["exploratory_top_only_10pct_within_m"]["500"],
        explore_top_only_10pct_within_1000m=d["exploratory_top_only_10pct_within_m"]["1000"],
        explore_top_only_10pct_within_2000m=d["exploratory_top_only_10pct_within_m"]["2000"],
        pair_length_m_median=d["pair_length_m_quartiles"][1],
        expected_pairs_reproduced=sum(p["reproduced"] for p in d["expected_pairs"]), expected_pairs=len(d["expected_pairs"]),
        dem5a_tiles=d["dem5a"]["tiles"], dem5a_tiles_404=d["dem5a"]["tiles_404"], seconds=d["seconds"]))
with open(OUT / "summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(r)

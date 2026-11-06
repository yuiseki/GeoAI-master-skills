"""Counts behind the report, from outputs/<box>_chains.csv (the main setting): outputs/chain_stats.csv.

  python3 scripts/chain_stats.py
"""

import csv
import statistics as st
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs"
rows = []
for key in ("kagawa", "fukuyama", "awaji"):
    R = list(csv.DictReader(open(OUT / f"{key}_chains.csv", encoding="utf-8")))
    ov = lambda r: sum(float(x) for x in r["overflowed_m3"].split(" > ")) if r["overflowed_m3"] else 0.0
    c1 = [r for r in R if int(r["overflowed"]) >= 1]
    c2 = [r for r in R if int(r["overflowed"]) >= 2]
    rows.append(dict(
        box=key, starts=len(R), chains_1plus=len(c1), chains_2plus=len(c2),
        # several starts can run down the same ponds: count the distinct last overflowed ponds
        chains_2plus_distinct_last_pond=len({r["overflowed_names"].split(" > ")[-1] + "@" + r["overflowed_m3"].split(" > ")[-1]
                                             for r in c2}),
        chains_2plus_overflowed_ge_start=sum(ov(r) >= float(r["start_m3"]) for r in c2),
        chains_2plus_people_ge_10=sum(float(r["people_chain"]) >= 10 for r in c2),
        chains_2plus_people_ge_100=sum(float(r["people_chain"]) >= 100 for r in c2),
        chains_2plus_people_median=round(st.median(float(r["people_chain"]) for r in c2), 1) if c2 else "",
        chains_2plus_people_single_median=round(st.median(float(r["people_single"]) for r in c2), 1) if c2 else "",
        chains_2plus_max_overflowed=max((int(r["overflowed"]) for r in c2), default=0),
        chains_2plus_stopped_leaving_area=sum(r["stop"] == "flow leaves the area or reaches no pond" for r in c2),
        # of those, the ones whose flow line really ends on the border of the grid (the rest end at the sea or a pit)
        chains_2plus_ending_at_grid_edge=sum(r["end_at_edge"] == "True" for r in c2),
        chains_2plus_stopped_holding=sum(r["stop"] == "next pond holds" for r in c2),
        chains_2plus_stopped_no_surface=sum(r["stop"] == "next pond has no water surface" for r in c2),
        chains_2plus_stopped_distance=sum(r["stop"] == "next pond beyond the distance" for r in c2),
        starts_stopped_no_surface=sum(r["stop"] == "next pond has no water surface" for r in R),
    ))
with open(OUT / "chain_stats.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(r)

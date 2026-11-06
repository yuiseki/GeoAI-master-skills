"""Exploratory (not in the plan): how the candidates (outputs/candidates.csv) look on their own.
Writes outputs/explore_exposure.csv.

  python3 scripts/explore_exposure.py
"""

import csv
import statistics as st
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs"
R = list(csv.DictReader(open(OUT / "candidates.csv", encoding="utf-8")))
rows = []
for b in ("kagawa", "fukuyama", "awaji"):
    rs = [r for r in R if r["box"] == b]
    ps = [float(r["people_single"]) for r in rs]
    pc = [float(r["people_chain"]) for r in rs]
    rows.append(dict(box=b, candidates=len(rs),
                     single_people_lt_1=sum(p < 1 for p in ps),
                     single_people_median=round(st.median(ps), 1), chain_people_median=round(st.median(pc), 1),
                     chain_people_ge_2x_single=sum(c >= 2 * max(s, 1) for s, c in zip(ps, pc)),
                     start_m3_median=round(st.median(float(r["start_m3"]) for r in rs)),
                     start_m3_ge_5000=sum(float(r["start_m3"]) >= 5000 for r in rs),
                     no_overflowed_pond_designated=sum(set(r["overflowed_designated"].split(" > ")) == {"no"} for r in rs),
))
with open(OUT / "explore_exposure.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(r)

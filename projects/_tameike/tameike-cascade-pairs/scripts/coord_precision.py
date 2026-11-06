"""Share of ledger points in each box given to 3 decimals or fewer (about 100 m): outputs/coord_precision.csv.

  python3 scripts/coord_precision.py   (reads outputs/<box>_ponds.csv)
"""

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs"
rows = []
for key in ("kagawa", "fukuyama", "awaji"):
    ps = list(csv.DictReader(open(OUT / f"{key}_ponds.csv", encoding="utf-8")))
    coarse = [p for p in ps if abs(float(p["lat"]) * 1000 - round(float(p["lat"]) * 1000)) < 1e-6
              and abs(float(p["lon"]) * 1000 - round(float(p["lon"]) * 1000)) < 1e-6]
    on_hole = lambda s: sum(p["placed"] == "hole" for p in s)
    fine = [p for p in ps if p not in coarse]
    rows.append(dict(box=key, ponds=len(ps), coarse_3dp=len(coarse), coarse_3dp_pct=round(100 * len(coarse) / len(ps), 1),
                     hole_pct_coarse=round(100 * on_hole(coarse) / len(coarse), 1) if coarse else "",
                     hole_pct_fine=round(100 * on_hole(fine) / len(fine), 1) if fine else ""))
with open(OUT / "coord_precision.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(r)

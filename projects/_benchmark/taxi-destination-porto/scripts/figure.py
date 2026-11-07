"""outputs/fig_curves.png: the validation error during training of the three runs, with the last-point baseline (M1) on
each run's validation set and the paper's custom-test error of the winning model.

  python3 scripts/figure.py
"""

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from porto import haversine
from run import ART, OUT

plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
runs = [("rand_mlp_s1", "M2 (全期間、CPU)", "#1d4ed8"), ("rand_noemb_s1", "M3 埋め込みなし (全期間、GPU)", "#60a5fa"),
        ("late_mlp_s1", "M2 (2014-03 まで、GPU)", "#b45309")]
t = np.load(ART / "trips.npz")
fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
for tag, label, color in runs:
    r = list(csv.DictReader(open(OUT / f"train_{tag}.csv", encoding="utf-8")))
    ax.plot([int(x["step"]) / 1000 for x in r], [float(x["valid_km"]) for x in r], color=color, label=label, lw=1.6)
for variant, color in (("rand", "#1d4ed8"), ("late", "#b45309")):
    s = np.load(ART / f"split_{variant}.npz")
    tr, n = s["valid_trip"], s["valid_n"]
    last, d = t["off"][tr] + n - 1, t["off"][tr + 1] - 1
    m1 = haversine(t["lat"][last], t["lon"][last], t["lat"][d], t["lon"][d]).mean()
    ax.axhline(m1, color=color, ls=":", lw=1.2)
    ax.text(302, m1, f"M1 最後の点 ({variant}) {m1:.2f}", va="center", fontsize=8, color=color)
ax.axhline(2.81, color="#6b7280", ls="--", lw=1)
ax.text(302, 2.81, "論文の優勝モデル 2.81 (自前の試験)", va="center", fontsize=8, color="#6b7280")
ax.set_xlabel("学習の step (千、1 step = 200 本の接頭)")
ax.set_ylabel("検証の平均誤差 (km、haversine)")
ax.set_xlim(0, 300)
ax.legend(fontsize=8, loc="upper right", bbox_to_anchor=(0.72, 1))
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "fig_curves.png", bbox_inches="tight")

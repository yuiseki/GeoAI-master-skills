"""outputs/fig_by_size.png from outputs/b1.csv and outputs/b2.csv: the S1-S2 difference of the water share and the
correlation of their changes (pond and date means removed), by pond size, with the 95 % intervals.

  uvx --python 3.12 --with matplotlib python scripts/figure.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "outputs"
for f in ("Noto Sans CJK JP", "Noto Sans CJK TC", "IPAexGothic"):
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break

b1 = list(csv.DictReader(open(OUT / "b1.csv", encoding="utf-8")))
b2 = list(csv.DictReader(open(OUT / "b2.csv", encoding="utf-8")))
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
x = range(len(b1))
labels = [f"{r['size_class']}\n池 {r['ponds']}" for r in b1]
v = [float(r["median_abs_diff"]) for r in b1]
a1.errorbar(x, v, yerr=[[vv - float(r["ci_low"]) for vv, r in zip(v, b1)], [float(r["ci_high"]) - vv for vv, r in zip(v, b1)]],
            fmt="o", color="#334155", capsize=4)
a1.set_xticks(list(x), labels, fontsize=8)
a1.set_ylabel("|S1 − S2| の中央値 (水面の割合)")
a1.set_title("B1: 水面の割合の差", fontsize=10)
a1.set_ylim(0, 0.5)
ok = [r for r in b2 if r.get("corr_twoway")]
xs = [i for i, r in enumerate(b2) if r.get("corr_twoway")]
c = [float(r["corr_twoway"]) for r in ok]
a2.errorbar(xs, c, yerr=[[cc - float(r["ci_low"]) for cc, r in zip(c, ok)], [float(r["ci_high"]) - cc for cc, r in zip(c, ok)]],
            fmt="o", color="#1d4ed8", capsize=4, label="二方向の平均を除いた相関")
a2.plot(xs, [float(r["perm_p975"]) for r in ok], "x", color="#9ca3af", label="日付の並べ替えの 97.5%")
a2.axhline(0, color="#9ca3af", linewidth=0.8)
a2.set_xticks(range(len(b2)), [f"{r['size_class']}\n池 {r['ponds']}" for r in b2], fontsize=8)
a2.set_title("B2: 増減の相関 (3 組以上ある池)", fontsize=10)
a2.legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "fig_by_size.png", dpi=150)

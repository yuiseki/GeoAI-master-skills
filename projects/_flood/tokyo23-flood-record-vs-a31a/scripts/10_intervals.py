"""Figure 4: the differences in capture@k_A with their 90% block-bootstrap intervals, for the main run and every
robustness run (C1: model - A31a, C2: A31a - random).

uvx --with numpy --with matplotlib python scripts/10_intervals.py
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"
sys.path.insert(0, str(HERE.parents[3] / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

RUNS = [("b1_main", "本解析 (100 m、2 km ブロック)"), ("rob_block_5km", "5 km ブロック"), ("rob_grid_250", "250 m 格子"),
        ("rob_grid_250_off125", "250 m 格子、125 m ずらし"), ("rob_grid_500", "500 m 格子"), ("rob_split_1990", "学習 1974-1989、試験 1990-2004"),
        ("rob_label_centre", "陽性 = 中心が記録の中"), ("rob_naisui", "内水の記録だけ"), ("rob_issui", "溢水の記録だけ"),
        ("rob_a31a_planned", "A31a 計画規模"), ("rob_a31a_max_0.5m", "A31a 最大規模 0.5 m 以上")]
PAIRS = [(("model_static", "a31a"), "C1: 記録から学んだ地図 − A31a"), (("a31a", "random"), "C2: A31a − でたらめ")]


def main():
    use_cjk_font()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), sharey=True)
    for ax, (pair, title) in zip(axes, PAIRS):
        for i, (name, label) in enumerate(RUNS):
            r = json.loads((OUT / f"{name}.json").read_text())
            d = next(d for d in r["diffs"] if (d["a"], d["b"]) == pair and abs(d["k"] - r["k_a31a"]) < 1e-12)
            y = len(RUNS) - 1 - i
            colour = "#1f77b4" if d["lo90"] > 0 else "#999999"
            ax.plot([d["lo90"], d["hi90"]], [y, y], color=colour, linewidth=2)
            ax.plot([d["diff"]], [y], "o", color=colour)
        ax.axvline(0, color="#333333", linewidth=0.8)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("capture@k_A の差 (点: 推定、線: 90% 区間)")
        ax.grid(axis="x", color="#dddddd")
    axes[0].set_yticks(range(len(RUNS)), [label for _, label in reversed(RUNS)])
    fig.suptitle("試験期間の記録で測った差 (試験期間は 1997〜2019 年、学習の区切りを変えた行だけ 1990〜2004 年。灰色: 区間が 0 をまたぐ)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_intervals.png", dpi=150)
    print(OUT / "fig4_intervals.png")


if __name__ == "__main__":
    main()

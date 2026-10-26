"""Per prefecture: autumn bear reports (log scale) and the summer temperature measures by year, read from the
exploratory table.

Usage:
    uvx --with matplotlib --with pandas python plot.py TABLE.csv OUT.png
"""

import sys

import pandas as pd


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(sys.argv[1])
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    names = {"akita": "秋田県", "gifu": "岐阜県", "kyoto": "京都府", "ishikawa": "石川県"}
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5))
    for ax, r in zip(axes.ravel(), ["akita", "gifu", "kyoto", "ishikawa"]):
        g = df[df.region == r].sort_values("year")
        ax.bar(g.year, g.autumn, color="#c4512a", alpha=0.8, label="秋 (9〜12 月) の通報")
        ax.set_yscale("log")
        ax.set_ylabel("通報 (対数)")
        ax2 = ax.twinx()
        ax2.plot(g.year, g.dT, color="#2f5d8a", marker="o", label="ΔT (前年の夏 − 前々年の夏)")
        ax2.plot(g.year, g.T_yoy, color="#5aa36e", marker="s", ls="--", label="気温の前年比 (当年の夏 − 前年の夏)")
        ax2.axhline(0, color="#888888", lw=0.8)
        ax2.set_ylabel("°C")
        ax.set_title(names[r])
        ax.set_xticks(g.year)
        ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    h1, l1 = axes[0, 0].get_legend_handles_labels()
    h2, l2 = axes[0, 0].get_figure().axes[4].get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.suptitle("県ごとの秋のクマ出没通報と、夏の最高気温の変化 (AgERA5)")
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(sys.argv[2], dpi=150)


if __name__ == "__main__":
    main()

"""MAE and bias by season for the chosen model and the previous-period value (Akita, development comparison B2),
read from dev_b2_by_season.csv.

Usage:
    uvx --with pandas --with matplotlib python plot_season.py BY_SEASON.csv OUT.png
"""

import sys

SEASONS = ["1 Jan-Mar", "2 Apr-May", "3 Jun-Aug", "4 Sep-Dec"]
LABELS = {"1 Jan-Mar": "1〜3 月", "2 Apr-May": "4〜5 月", "3 Jun-Aug": "6〜8 月", "4 Sep-Dec": "9〜12 月"}
MODELS = [("naive", "前週値 naive", "#9a9a9a"), ("hgb_nb", "選んだモデル hgb_nb", "#c4512a")]


def season_table(df, h, models):
    """mae and bias as season x (measure, model) for one horizon."""
    d = df[(df.h == h) & df.model.isin(models)]
    missing = [(m, s) for m in models for s in SEASONS if d[(d.model == m) & (d.season == s)].empty]
    if missing:
        raise SystemExit(f"no rows for {missing} at h = {h}")
    t = d.pivot(index="season", columns="model", values=["mae", "bias"]).loc[SEASONS]
    return t.reindex(columns=[(v, m) for v in ("mae", "bias") for m in models])


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    df, out = pd.read_csv(sys.argv[1]), sys.argv[2]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    x = np.arange(len(SEASONS))
    for ax, h in zip(axes, (1, 4)):
        t = season_table(df, h, [m for m, _, _ in MODELS])
        for k, (m, name, col) in enumerate(MODELS):
            bars = ax.bar(x + (k - 0.5) * 0.38, t[("mae", m)], 0.36, color=col, label=name)
            ax.bar_label(bars, labels=[f"{v:.2f}\n偏り {b:+.2f}" for v, b in zip(t[("mae", m)], t[("bias", m)])],
                         fontsize=7, padding=2)
        ax.set_xticks(x, [LABELS[s] for s in SEASONS])
        ax.set_title(f"{h} 週先", loc="left", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("MAE (件 / 市町村 / 週)")
    axes[0].set_ylim(0, 13.5)
    axes[0].legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle("季節ごとの外れ方 (秋田、起点 177、偏りは予測 − 観測の平均。負は小さめに外す)", x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main()

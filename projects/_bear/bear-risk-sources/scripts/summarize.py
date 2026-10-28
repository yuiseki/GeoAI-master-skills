"""Summaries of the leave-regions-out matrix: mean capture@5% per variant and number of training regions, the paired
difference from `base` on the same (training set, target) pairs, and per target region. Writes CSVs and a figure.

Usage:
    uvx --with pandas --with matplotlib python summarize.py OUT_DIR MATRIX.csv [MATRIX.csv ...]
"""

import sys

import pandas as pd

ORDER = ["base", "bldg_none", "bldg_ovt", "road_none", "road_ovt", "road_ksj", "river_none", "river_ovt", "river_ksj", "clim", "combo_clim_nobldg", "combo_clim_bldgovt"]
LABEL = {"base": "基準 (OSM)", "bldg_none": "建物なし", "bldg_ovt": "建物 Overture", "road_none": "道路なし", "road_ovt": "道路 Overture",
         "road_ksj": "道路 国土数値情報", "river_none": "川なし", "river_ovt": "川 Overture", "river_ksj": "川 国土数値情報", "clim": "平年値を足す", "combo_clim_nobldg": "平年値 + 建物なし", "combo_clim_bldgovt": "平年値 + 建物 Overture"}


# one hue family per axis: buildings green, roads purple and brown, rivers grey, climate blue
STYLE = {"base": ("#111111", "-", 2.8), "bldg_none": ("#2e8b57", "--", 1.4), "bldg_ovt": ("#7fbf7f", "--", 1.4),
         "road_none": ("#6a3d9a", ":", 1.6), "road_ovt": ("#b294c7", "--", 1.4), "road_ksj": ("#8c564b", "--", 1.4),
         "river_none": ("#555555", ":", 1.4), "river_ovt": ("#888888", "--", 1.2), "river_ksj": ("#bbbbbb", "--", 1.2),
         "clim": ("#1f5fa8", "-", 2.0), "combo_clim_nobldg": ("#4f9fe0", "-.", 1.8), "combo_clim_bldgovt": ("#0b3b70", "-.", 1.8)}


def summarise(df):
    mean = df.groupby(["variant", "k"]).capture5.mean().unstack()
    base = df[df.variant == "base"].set_index(["train", "target"]).capture5
    d = df[df.variant != "base"].join(base.rename("base"), on=["train", "target"])
    d["diff"] = d.capture5 - d.base
    diff = d.groupby(["variant", "k"])["diff"].agg(["mean", "min", "max", "count"])
    wins = d.groupby("variant")["diff"].apply(lambda s: int((s > 0).sum())).rename("pairs_better")
    per_target = df.groupby(["variant", "target"]).capture5.mean().unstack()
    return mean, diff, wins, per_target


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = sys.argv[1]
    df = pd.concat([pd.read_csv(p) for p in sys.argv[2:]], ignore_index=True).drop_duplicates(["variant", "train", "target"])
    mean, diff, wins, per_target = summarise(df)
    order = [v for v in ORDER if v in mean.index] + [v for v in mean.index if v not in ORDER]
    mean.loc[order].round(3).to_csv(f"{out}/mean_by_k.csv")
    diff.round(3).to_csv(f"{out}/diff_from_base.csv")
    per_target.loc[order].round(3).to_csv(f"{out}/per_target.csv")
    wins.to_csv(f"{out}/pairs_better_than_base.csv")
    print(mean.loc[order].round(3).to_string())
    print(diff.round(3).to_string())
    print(wins.to_string())
    print(per_target.loc[order].round(3).to_string())
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    for v in order:
        col, ls, lw = STYLE.get(v, ("#999999", "--", 1.0))
        ax.plot(mean.columns, mean.loc[v], marker="o", ls=ls, lw=lw, color=col, label=LABEL.get(v, v))
    ax.axhline(0.05, color="#444444", lw=0.8, ls=":")
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("学習に使った地域の数")
    ax.set_ylabel("伏せた地域の capture@5% (平均)")
    ax.set_title("学習に使っていない地域を当てる: データの出どころと地域の数")
    ax.legend(fontsize=8, ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{out}/sources-by-k.png", dpi=150)


if __name__ == "__main__":
    main()

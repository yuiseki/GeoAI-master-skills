"""Figures for report.md: weekly reports in Akita with the frozen forecast, and the MAE of each model.

Values are read from the weekly table, the frozen forecast and the scores files written by evaluate.py,
and the plotted values are written next to each PNG as JSON.

Usage:
    uvx --with matplotlib --with pandas --with numpy --with pyarrow python plot.py ARTIFACTS_DIR OUTPUTS_DIR
"""

import json
import sys

import numpy as np
import pandas as pd


def mae_values(scores_path, models, horizons):
    s = json.load(open(scores_path))
    return {m: [s[f"{m}|h{h}"]["mae"] for h in horizons] for m in models}


def weekly_totals(df):
    return df.groupby("week_start").bear.sum()


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    art, out = sys.argv[1], sys.argv[2]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]

    # figure 1: weekly totals with the frozen forecast
    wk = pd.read_parquet(f"{art}/akita_week.parquet")
    tot = weekly_totals(wk)
    tot.index = pd.to_datetime(tot.index)
    fz = pd.read_parquet(f"{art}/frozen/akita_frozen_2026-10-26.parquet")
    cand = fz[fz.model == "hgb_nb"].groupby("target_week").pred.sum()
    cand.index = pd.to_datetime(cand.index)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(tot.index, tot.values + 1, color="#444444", lw=1.2, label="観測 (週の通報件数 + 1)")
    ax.plot(cand.index, cand.values + 1, color="#d95f02", lw=2, marker="o", ms=4, label="凍結した予測 (hgb_nb、2026-09-21 起点)")
    ax.set_yscale("log")
    ax.set_ylabel("秋田県の週の通報件数 + 1 (対数)")
    ax.set_title("秋田県のクマ出没通報 (週、25 市町村の合計)")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{out}/akita-weekly-and-frozen.png", dpi=150)
    plt.close(fig)
    json.dump({"observed_weeks": len(tot), "last_observed_week": str(tot.index[-1].date()),
               "observed_max": int(tot.max()), "frozen_total_by_week": {str(k.date()): float(v) for k, v in cand.items()}},
              open(f"{out}/akita-weekly-and-frozen.json", "w"), indent=1, ensure_ascii=False)

    # figure 2: MAE of the models
    ak_models = ["naive", "mean_short", "seasonal_3y", "glm", "glm_nb", "hgb", "hgb_nb", "hier_hgb"]
    gi_models = ["naive", "seasonal_3y", "glm", "hgb"]
    ak = mae_values(f"{art}/eval_b2_scores.json", ak_models, [1, 2, 4])
    gi = mae_values(f"{art}/gifu_models_scores.json", gi_models, [1, 2, 3])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [len(ak_models), len(gi_models)]})
    for ax, vals, hs, title, unit in ((axes[0], ak, [1, 2, 4], "秋田 (市町村 × 週)", "週先"), (axes[1], gi, [1, 2, 3], "岐阜 (市町村 × 月)", "か月先")):
        names = list(vals)
        x = np.arange(len(names))
        w = 0.27
        for k, h in enumerate(hs):
            ax.bar(x + (k - 1) * w, [vals[n][k] for n in names], w, label=f"{h} {unit}")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=35, ha="right")
        ax.set_title(title)
        ax.set_ylabel("MAE (件 / 市町村 / 期間)")
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{out}/mae-by-model.png", dpi=150)
    plt.close(fig)
    json.dump({"akita_weekly_b2": ak, "gifu_monthly_exploratory": gi}, open(f"{out}/mae-by-model.json", "w"), indent=1, ensure_ascii=False)
    print("wrote figures")


if __name__ == "__main__":
    main()

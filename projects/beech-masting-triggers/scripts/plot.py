"""Figures of the report, from the outputs of the blocks (no recomputation):
index-by-year.png, rmse-by-model.png, confirm-predictions.png, cue-correlations.png.

From repository root:
    uvx --with matplotlib --with pandas python projects/beech-masting-triggers/scripts/plot.py \
      projects/beech-masting-triggers/outputs
"""

import argparse
import json
from pathlib import Path

import pandas as pd

PREFS = [("青森県", "#3b6e8f"), ("岩手県", "#6a8f3b"), ("宮城県", "#8a5a9e"), ("秋田県", "#c4512a"), ("山形県", "#b08a2e")]
MODEL_LABELS = {"M0": "M0 県の平均", "M1": "M1 前年の結実", "M2": "M2 前の夏", "M3": "M3 ΔT", "M4": "M4 2 つの夏",
                "M5": "M5 前の夏 + 前年の結実", "M6": "M6 ΔT + 前年の結実", "M7": "M7 2 つの夏 + 前年の結実 + 春"}


def rmse_rows(b1, b2):
    """[(model, dev LOYO RMSE, confirmation RMSE)] in model order."""
    conf = b2["auxiliary"]["refit_on_dev"]
    return [(m, b1["loyo_rmse"][m], conf[m]["rmse"]) for m in MODEL_LABELS]


def cue_rows(b4, b5):
    """[(label, rho, lo, hi, confirmatory)] for the confirmation years."""
    a4, a5 = b4["auxiliary_exploratory"], b5["auxiliary_exploratory"]
    c = b4["Ts_lag1_vs_flowering"]
    rows = [("C2: 前の夏 Ts(t−1) と開花時", c["spearman"], *c["ci90"], True)]
    for key, label in (("Ts_lag1 vs F", "前の夏 Ts(t−1) と結実時"), ("dT vs flower", "ΔT と開花時"),
                       ("dT vs F", "ΔT と結実時"), ("F_lag vs flower", "前年の結実 F(t−1) と開花時"),
                       ("F_lag vs F", "前年の結実 F(t−1) と結実時"), ("Tsp vs loss", "春の最低気温と開花から結実への減り")):
        rows.append((label, a4[key]["spearman"], *a4[key]["ci90"], False))
    for key, label in (("S1_t-1", "C3: 衛星 S1 前の夏の地表面温度と結実時"), ("S2_t-1", "C3: 衛星 S2 前年の純一次生産量と結実時")):
        r = b5["confirmatory"][key]
        rows.append((label, r["spearman"], *r["ci95"], True))
    rows.append(("衛星 S3 展葉の日と開花から結実への減り", a5["S3 vs loss"]["spearman"], *a5["S3 vs loss"]["ci90"], False))
    return rows


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    o = a.outputs
    load = lambda n: json.loads((o / n).read_text(encoding="utf-8"))  # noqa: E731
    b1, b2, b4, b5 = load("b1_frozen_models.json"), load("b2_b3_confirm.json"), load("b4_stage.json"), load("b5_satellite.json")
    idx = pd.read_csv(o / "tohoku_beech_index.csv")
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]

    # 1. the index by year
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axvspan(1989.5, 2008.5, color="#eef2f6")
    ax.axvspan(2008.5, 2026.5, color="#fbf1e8")
    for pref, col in PREFS:
        s = idx[(idx.pref == pref) & (idx.stage == "fruiting")]
        ax.plot(s.year, s["index"], "-o", ms=3, lw=1.2, color=col, label=pref)
    for y, lab in ((1999, "開発期間 (1990〜2008 年)"), (2017.5, "確認期間 (2009〜2026 年)")):
        ax.text(y, 5.15, lab, ha="center", fontsize=9, color="#444444")
    for v, lab in ((3.5, "豊作"), (2.0, "並作"), (1.0, "凶作")):
        ax.axhline(v, color="#999999", lw=0.6, ls=":")
        ax.text(2026.8, v, lab, fontsize=8, va="center", color="#666666")
    ax.set_ylim(-0.1, 5.4)
    ax.set_xlim(1988.5, 2027.5)
    ax.set_ylabel("結実時の豊凶指数 (0〜5)")
    ax.legend(ncol=5, fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.1))
    ax.set_title("東北 5 県のブナの結実時の豊凶指数 (東北森林管理局)", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(o / "index-by-year.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. RMSE by model, development (LOYO) and confirmation
    rows = rmse_rows(b1, b2)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ys = list(range(len(rows)))[::-1]
    for y, (m, dev, conf) in zip(ys, rows):
        ax.barh(y + 0.18, dev, 0.34, color="#9fb3c8")
        ax.barh(y - 0.18, conf, 0.34, color="#c4512a" if m == b1["chosen"] else "#e2a27f")
        ax.text(conf + 0.02, y - 0.18, f"{conf:.3f}", va="center", fontsize=8)
        ax.text(dev + 0.02, y + 0.18, f"{dev:.3f}", va="center", fontsize=8, color="#555555")
    ax.set_yticks(ys, [MODEL_LABELS[m] + (" (選択)" if m == b1["chosen"] else "") for m, *_ in rows], fontsize=9)
    from matplotlib.patches import Patch

    ax.legend(handles=[Patch(color="#9fb3c8", label="開発期間、年を伏せた交差検証"),
                       Patch(color="#e2a27f", label="確認期間、開発期間で当てて凍結")],
              fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.1), ncol=2)
    ax.set_xlabel("結実時の豊凶指数の RMSE (小さいほど良い)")
    ax.set_xlim(0, 1.75)
    ax.set_title("開発期間で最も良かった M7 は、確認期間では前年の結実だけの M1 に負けた", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(o / "rmse-by-model.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. confirmation-period predictions, mean over the prefectures of a year
    pr = pd.DataFrame(b2["per_row"]).groupby("year")[["F", "M0", "M1", b1["chosen"]]].mean()
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.plot(pr.index, pr.F, "-o", color="#222222", lw=1.6, ms=4, label="観測 (5 県の平均)")
    ax.plot(pr.index, pr.M1, "--", color="#3b6e8f", lw=1.3, label="M1 前年の結実")
    ax.plot(pr.index, pr[b1["chosen"]], "-", color="#c4512a", lw=1.3, label=f"{b1['chosen']} (開発期間で選択)")
    ax.set_ylabel("結実時の豊凶指数")
    ax.set_xticks(range(2009, 2027, 2))
    ax.legend(fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.12), ncol=3)
    ax.set_title("確認期間の予測と観測 (年ごとの 5 県の平均)", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(o / "confirm-predictions.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 4. correlations of the cues in the confirmation years
    rows = cue_rows(b4, b5)
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ys = list(range(len(rows)))[::-1]
    for y, (lab, r, lo, hi, conf) in zip(ys, rows):
        col = "#1f4e79" if conf else "#9aa9b8"
        ax.plot([lo, hi], [y, y], color=col, lw=2)
        ax.plot(r, y, "o", color=col, ms=6)
        ax.text(1.03, y, f"{r:+.2f} ({lo:+.2f}〜{hi:+.2f})", va="center", fontsize=8)
    ax.axvline(0, color="#444444", lw=0.8)
    ax.set_yticks(ys, [r[0] for r in rows], fontsize=9)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("順位相関 (確認期間の県 × 年)。濃い色は先に決めた判定 (C2 は 90%、C3 は 95% 区間)、薄い色は探索 (90%)")
    ax.set_title("確認期間で、前年の結実と ΔT は豊凶と並び、前の夏の気温だけでは弱い", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(o / "cue-correlations.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Figures of the report, from the saved outputs only (no refitting):

    sites-blocks.png      the 98 sites in EPSG:6691 by elevation, with the 50 km blocks
    rmse-by-scheme.png    RMSE of each model in A, B, C, development period and confirmation period
    diff-vs-m1.png        confirmation RMSE minus M1's, 90% year-bootstrap interval, per model and scheme
    rmse-by-year.png      confirmation RMSE per target year in C (M1, M2, G*) and the mean observed rank
    permutations.png      F1 (climate years shuffled, C) and F2 (terrain shuffled between sites, B): the actual RMSE
                          against the median and 5% point of the 200 shuffles (the shuffles themselves were not kept)

From repository root:
    uvx --with matplotlib --with pandas --with pyproj --with pyarrow python \
      projects/beech-masting-spatial-proxy/scripts/plot.py projects/beech-masting-spatial-proxy/outputs \
      artifacts/beech-masting-spatial-proxy
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams["font.family"] = "Noto Sans CJK JP"
MODELS = ["M0", "M1", "M2", "M3", "M4", "M5", "M7"]
LABEL = {"M0": "M0 地点の基準", "M1": "M1 前年の結実", "M2": "M2 + ΔT", "M3": "M3 + 地形", "M4": "M4 + 水分 (WB)",
         "M5": "M5 + 交互作用", "M7": "M7 前年 + 2 つの夏 + 春 (補助)", "M1y": "M1y 前年 + 年の切片 (補助、B)"}
SCHEME = {"A": "A 未知の年", "B": "B 未知の地点", "C": "C 未知の地点 × 年"}


def bars_table(dev, conf):
    """[(scheme, model, dev rmse, confirmation rmse)]."""
    out = []
    for s in "ABC":
        for m in MODELS + (["M1y"] if s == "B" else []):
            out.append((s, m, dev[s][m]["rmse"], conf["scores"][s][m]["rmse"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    args = ap.parse_args()
    o = args.outputs
    choice = json.loads((o / "b1_frozen_choice.json").read_text())
    dev = json.loads((o / "b1_dev_scores.json").read_text())[f"r{choice['radius']}_{choice['water']}"]
    conf = json.loads((o / "b2_confirm.json").read_text())
    checks = json.loads((o / "b3_checks.json").read_text())
    g = choice["g_star"]

    # 1 sites and blocks
    from pyproj import Transformer

    t = pd.read_csv(o / "terrain_sites.csv")
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:6691", always_xy=True).transform(t.lon.to_numpy(), t.lat.to_numpy())
    fig, ax = plt.subplots(figsize=(5.5, 7))
    sc = ax.scatter(x / 1000, y / 1000, c=t.alt, cmap="viridis", s=28, edgecolor="k", linewidth=0.3)
    for v in range(int(x.min() // 50000), int(x.max() // 50000) + 2):
        ax.axvline(v * 50, color="0.8", lw=0.6, zorder=0)
    for v in range(int(y.min() // 50000), int(y.max() // 50000) + 2):
        ax.axhline(v * 50, color="0.8", lw=0.6, zorder=0)
    ax.set_aspect("equal")
    ax.set_xlabel("東 (km、EPSG:6691)")
    ax.set_ylabel("北 (km、EPSG:6691)")
    ax.set_title("東北の 98 地点と 50 km のブロック")
    fig.colorbar(sc, ax=ax, shrink=0.7, label="標高 (m、Dryad の Altitude)")
    fig.tight_layout()
    fig.savefig(o / "sites-blocks.png", dpi=150)
    plt.close(fig)

    # 2 RMSE by scheme
    rows = bars_table(dev, conf)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2))
    for ax, s in zip(axes, "ABC"):
        r = [q for q in rows if q[0] == s]
        idx = range(len(r))
        ax.barh([i + 0.2 for i in idx], [q[2] for q in r], height=0.4, color="#9ec5e8", label="開発期間 (t = 1990〜1999)")
        ax.barh([i - 0.2 for i in idx], [q[3] for q in r], height=0.4, color="#2b6ca3", label="確認期間 (t = 2000〜2008)")
        ax.set_yticks(list(idx), [LABEL[q[1]] + (" = G*" if q[1] == g else "") for q in r], fontsize=8)
        ax.axvline(conf["scores"][s]["M1"]["rmse"], color="#c4512a", lw=1, ls="--")
        ax.set_title(f"{SCHEME[s]} (確認 {conf['scores'][s]['M1']['n']} 行)")
        ax.set_xlabel("RMSE (評価 0〜3)")
        ax.set_xlim(0.6, 1.4)
        ax.invert_yaxis()
    axes[0].legend(loc="lower right", fontsize=8)
    fig.suptitle("モデルごとの RMSE。破線は確認期間の M1")
    fig.tight_layout()
    fig.savefig(o / "rmse-by-scheme.png", dpi=150)
    plt.close(fig)

    # 3 differences against M1 in the confirmation period
    fig, ax = plt.subplots(figsize=(8, 5))
    ylab, k = [], 0
    colours = {"A": "#6a8f3b", "B": "#3b6e8f", "C": "#c4512a"}
    for s in "ABC":
        for m in ["M2", "M3", "M4", "M5", "M7"] + (["M1y"] if s == "B" else []):
            b = conf["aux_vs_M1"][s][m]
            ax.errorbar(b["diff"], k, xerr=[[b["diff"] - b["lo90"]], [b["hi90"] - b["diff"]]], fmt="o",
                        color=colours[s], ms=6 if m == g else 4, mfc=colours[s] if m == g else "white")
            ylab.append(f"{s}  {LABEL[m]}" + (" = G*" if m == g else ""))
            k += 1
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(range(k), ylab, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("RMSE − RMSE(M1)、確認期間 (負なら M1 より良い)。線は 90% 区間 (年の復元抽出、9 年)")
    fig.tight_layout()
    fig.savefig(o / "diff-vs-m1.png", dpi=150)
    plt.close(fig)

    # 4 RMSE by year in C
    by = conf["rmse_by_year"]["C"]
    years = sorted(int(y) for y in by["M1"])
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for m, c in (("M1", "#c4512a"), ("M2", "#6a8f3b"), (g, "#2b6ca3")):
        ax.plot(years, [by[m][str(y)] if str(y) in by[m] else by[m][y] for y in years], marker="o", color=c, label=LABEL[m])
    obs = pd.read_parquet(args.art / "confirm_predictions.parquet")
    obs = obs[(obs.scheme == "C") & (obs.model == "M1")].drop_duplicates(["ID", "t"]).groupby("t").y.mean()
    ax2 = ax.twinx()
    ax2.bar(obs.index, obs.to_numpy(), color="0.85", zorder=0, width=0.6)
    ax2.set_ylabel("観測の評価の平均 (棒)")
    ax2.set_ylim(0, 3)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.set_xlabel("目的の年 t")
    ax.set_ylabel("RMSE (C 未知の地点 × 年)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(o / "rmse-by-year.png", dpi=150)
    plt.close(fig)

    # 5 permutations (summaries only)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for k, (key, title) in enumerate((("F1_climate_years_C", "F1 気象の年を並べ替え (C)"),
                                      ("F2_terrain_sites_B", "F2 地形を地点の間で並べ替え (B)"))):
        c = checks[key]
        ax.plot([c["perm_p05"], c["perm_median"]], [k, k], color="0.6", lw=6, solid_capstyle="butt")
        ax.plot(c["perm_p05"], k, "|", color="k", ms=18)
        ax.plot(c["actual"], k, "o", color="#c4512a", ms=9)
        ax.text(c["actual"], k + 0.25, f"実際 {c['actual']:.3f}", ha="center", fontsize=8)
        ax.text(c["perm_median"], k - 0.3, f"5% 点 {c['perm_p05']:.3f}、中央値 {c['perm_median']:.3f}", ha="right",
                fontsize=8)
    ax.set_yticks([0, 1], ["F1 気象の年を並べ替え (C)", "F2 地形を地点の間で並べ替え (B)"])
    ax.set_ylim(-0.7, 1.7)
    ax.set_xlabel(f"確認期間の RMSE (G* = {g})。灰色は並べ替え 200 回の 5% 点から中央値")
    fig.tight_layout()
    fig.savefig(o / "permutations.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()

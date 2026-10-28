"""Figures of the report, from the saved outputs (no recomputation of the models):
exposure-map.png, dev-confirm-by-model.png, permutations.png, positives-by-class.png, positives-exposure-2025-2026.png.

From repository root:
    uvx --with matplotlib --with numpy python projects/akita-bear-mast-exposure/scripts/plot.py \
      artifacts/akita-bear-risk-grid-100m artifacts/akita-bear-mast-exposure projects/akita-bear-mast-exposure/outputs
"""

import json
import sys

import numpy as np

MODELS = ["M1", "M2", "M3", "M4", "M5"]
LABELS = {"M1": "M1 beech", "M2": "M2 beech_mizunara", "M3": "M3 mizunara", "M4": "M4 konara", "M5": "M5 beech_oak"}
CLASS_COLORS = ["#c9c9c9", "#cfe0c3", "#9cc58c", "#5d9d55", "#2c6a2f"]


def diff_rows(conf, target, variant="retrospective"):
    """[(model, diff, lo90, hi90)] of capture@5% against M0 for one target year."""
    r = conf["targets"][str(target)][variant]
    return [(m, r[m]["diff_capture@5%"]["diff"], r[m]["diff_capture@5%"]["lo90"], r[m]["diff_capture@5%"]["hi90"]) for m in r]


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bear, art, o = sys.argv[1:4]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    load = lambda n: json.load(open(f"{o}/{n}", encoding="utf-8"))  # noqa: E731
    dev, conf, fz, dg = load("b1_dev_scores.json"), load("b3_confirm.json"), load("b4_falsification.json"), load("b5_diagnostics.json")
    spec = load("b1_frozen_spec.json")
    r = str(spec["radius_m"])

    # 1. exposure map (the frozen beech_oak and the four categories at the frozen radius)
    e = np.load(f"{art}/exposure.npz")
    muni = np.load(f"{bear}/grid_mask.npz")["muni"]
    fig, axes = plt.subplots(1, 5, figsize=(15, 4.4))
    for ax, c in zip(axes, ["beech_oak", "beech", "beech_mizunara", "mizunara", "konara"]):
        a = np.where(muni >= 0, np.nan_to_num(e[f"{c}_fraction_{r}"], nan=0.0), np.nan)
        im = ax.imshow(a, origin="lower", cmap="YlGn", vmin=0, vmax=0.8 if c == "beech_oak" else 0.5, interpolation="nearest")
        ax.set_title(f"{c} ({int(r) // 1000} km)" if int(r) >= 1000 else f"{c} ({r} m)", fontsize=10, loc="left")
        ax.set_axis_off()
        fig.colorbar(im, ax=ax, shrink=0.6, pad=0.01)
    fig.suptitle("秋田県の 100 m セルごとの、半径の中の植生図の範囲に占めるブナ・ナラ類の群落の面積の割合", x=0.02, y=1.02, ha="left", fontsize=11)
    fig.savefig(f"{o}/exposure-map.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    # 2. development and confirmation differences by model
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    dv = dev["by_radius"][r]
    m0 = dev["M0"]["capture@5%"]
    dev_rows = [(m, dv[m]["metrics"]["capture@5%"] - m0, None, None) for m in MODELS]
    for ax, (title, rows) in zip(axes, (("2024 年度 (開発、区間は M5 だけ)", dev_rows),
                                        ("2025 年度 (確認 1)", diff_rows(conf, 2025)), ("2026 年度 4〜9 月 (確認 2)", diff_rows(conf, 2026)))):
        for i, (m, d, lo, hi) in enumerate(rows):
            col = "#c4512a" if m == "M5" else "#7a8aa0"
            ax.plot([i], [d * 100], "o", color=col)
            if lo is not None:
                ax.plot([i, i], [lo * 100, hi * 100], "-", color=col, lw=2)
        if title.startswith("2024"):
            dd = dv["M5"]["diff_vs_M0_capture@5%"]
            ax.plot([4, 4], [dd["lo90"] * 100, dd["hi90"] * 100], "-", color="#c4512a", lw=2)
        ax.axhline(0, color="#444444", lw=0.7)
        ax.set_xticks(range(5), MODELS)
        ax.set_title(title, fontsize=10, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("capture@5% の差 (M − B_env、ポイント)")
    h = conf["H"]["verdict"]
    fig.suptitle(f"mast_scarcity × exposure を足しても、上位 5% に入る陽性のセルはほとんど変わらない (主の仮説 H: {h}、線は 90% 区間)",
                 x=0.02, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{o}/dev-confirm-by-model.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. permutations
    fig, axes = plt.subplots(2, 2, figsize=(12, 6.4))
    for j, t in enumerate(("2025", "2026")):
        f1, f2 = fz["F1_year"][t], fz["F2_spatial"][t]
        ax = axes[0, j]
        ax.plot(range(len(f1["perm_values"])), np.array(f1["perm_values"]) * 100, "o", color="#9fb3c8", ms=4, label="年を入れ替えた 23 通り")
        ax.axhline(f1["true"] * 100, color="#c4512a", lw=1.5, label=f"本当の対応 {f1['true']:.4f}")
        ax.set_title(f"F1 年の並べ替え {t} 年度: {'通る' if f1['passes'] else '通らない'} (本当以上 {f1['n_reach_true']}/23)", fontsize=10, loc="left")
        ax.set_ylabel("M5 の capture@5% (%)")
        ax.legend(fontsize=8, frameon=False)
        ax = axes[1, j]
        ax.hist(np.array(f2["perm_values"]) * 100, bins=25, color="#cfd8e3", edgecolor="#9fb3c8")
        ax.axvline(f2["true"] * 100, color="#c4512a", lw=1.5, label=f"本当の配置 {f2['true']:.4f}")
        ax.axvline(f2["perm_p95"] * 100, color="#444444", lw=0.8, ls="--", label=f"並べ替えの 95% 点 {f2['perm_p95']:.4f}")
        ax.set_title(f"F2 植生の 10 km タイルの並べ替え {t} 年度: {'通る' if f2['passes'] else '通らない'}", fontsize=10, loc="left")
        ax.set_xlabel("M5 の capture@5% (%)")
        ax.legend(fontsize=8, frameon=False)
    for ax in axes.flat:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{o}/permutations.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 4. positive rate and B_env miss rate by exposure class, by year
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    years = ["2023", "2024", "2025", "2026"]
    w = 0.16
    for q in range(5):
        pr = [dg["by_year"][t]["classes"][q]["positive_rate"] * 1000 for t in years]
        mr = [dg["by_year"][t]["classes"][q]["b_env_miss_rate"] for t in years]
        xs = np.arange(4) + (q - 2) * w
        axes[0].bar(xs, pr, w, color=CLASS_COLORS[q], label=f"Q{q}", edgecolor="#555555", lw=0.3)
        axes[1].bar(xs, mr, w, color=CLASS_COLORS[q], edgecolor="#555555", lw=0.3)
    lab = [f"{t}\n不足 {dg['by_year'][t]['mast_scarcity']:.1f}" for t in years]
    for ax in axes:
        ax.set_xticks(range(4), lab)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("陽性のセルの割合 (‰)")
    axes[0].set_title("exposure の階級ごとの陽性の割合 (Q0 = 0、Q1〜Q4 = 正の値の 4 分位)", fontsize=10, loc="left")
    axes[0].legend(fontsize=8, frameon=False, ncol=5, loc="upper left")
    axes[1].set_ylabel("陽性のうち B_env の上位 5% の外の割合")
    axes[1].set_title("階級ごとの B_env の取り逃し (探索。2023 年度は B_env の学習の年で in-sample)", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(f"{o}/positives-by-class.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 5. exposure of the positives by region, 2025 and 2026
    fig, ax = plt.subplots(figsize=(10, 4))
    regs = list(dg["regions"])
    for j, t in enumerate(("2025", "2026")):
        vals = [dg["by_year"][t]["by_region"][rg]["exposure_of_positives"]["mean"] for rg in regs]
        npos = [dg["by_year"][t]["by_region"][rg]["positives"] for rg in regs]
        xs = np.arange(len(regs)) + (j - 0.5) * 0.35
        ax.bar(xs, vals, 0.35, color=["#c4512a", "#3b6e8f"][j], label=f"{t} 年度の陽性のセル (不足 {dg['by_year'][t]['mast_scarcity']:.1f})")
        for x, v, n in zip(xs, vals, npos):
            ax.text(x, v + 0.005, f"{n:,}", ha="center", fontsize=7)
    ax.plot(np.arange(len(regs)), [dg["regions"][rg]["exposure"]["mean"] for rg in regs], "k_", ms=28, mew=2, label="地域の全てのセル")
    ax.set_xticks(range(len(regs)), regs)
    ax.set_ylabel(f"beech_oak ({int(r) // 1000} km) の平均")
    ax.set_title("地域ごとの、陽性のセルの exposure の平均 (数字は陽性のセルの数)", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{o}/positives-exposure-2025-2026.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

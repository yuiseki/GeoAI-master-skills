"""The report's figures that are not maps: capture@5% of the models and the baselines in the two test years, and the
share of cells with a report by distance to the forest edge and to a building (BY2025).

Usage:
    ... python plot_figures.py OUTPUTS_DIR
"""

import json
import sys

BUILDING = ["建物のあるセル", "建物の隣のセル", "建物まで 100〜300 m", "建物まで 300 m〜1 km", "建物まで 1 km 超"]
EDGE = ["森の中 1 km 超", "森の中 300 m〜1 km", "森の中 100〜300 m", "森の縁のセル", "森の隣のセル", "森まで 100〜300 m",
        "森まで 300 m〜1 km", "森まで 1 km 超"]
MODELS = [("B_env", "環境のモデル\nB_env"), ("M_full", "環境と過去の通報\nM_full"), ("B_hist", "過去の通報の密度\nB_hist"),
          ("B_pop", "人口\nB_pop")]
TESTS = [("b2_confirm_2023-2024_to_2025.json", "2025 年度 (2023〜2024 年度で学習)", "#7a8fa6"),
         ("b3_confirm_2023-2025_to_2026.json", "2026 年度の 4〜9 月 (2023〜2025 年度で学習)", "#1f4e79")]


def edge_matrix(df):
    """(share with a report, cells) as building class x forest-edge class tables, the rows ending with all buildings."""
    df = df[df.forest_edge != "(all)"]
    share = df.pivot(index="building", columns="forest_edge", values="share_with_report")
    cells = df.pivot(index="building", columns="forest_edge", values="cells")
    rows = BUILDING + ["(all)"]
    missing = [(b, e) for b in rows for e in EDGE if b not in share.index or e not in share.columns or share.isna().at[b, e]]
    if missing:
        raise SystemExit(f"classes missing from the table: {missing}")
    return share.loc[rows, EDGE], cells.loc[rows, EDGE]


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    out = sys.argv[1]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(MODELS))
    for k, (f, label, colour) in enumerate(TESTS):
        d = json.load(open(f"{out}/{f}"))
        vals = [d[m]["capture@5%"] for m, _ in MODELS]
        bars = ax.bar(x + (k - 0.5) * 0.38, vals, 0.36, color=colour, label=label)
        ax.bar_label(bars, labels=[f"{v:.3f}" for v in vals], fontsize=8, padding=2)
    ax.axhline(0.05, color="#888888", lw=1, ls="--")
    ax.text(len(MODELS) - 0.5, 0.055, "でたらめ 0.05", ha="right", va="bottom", fontsize=8, color="#666666")
    ax.set_xticks(x, [lab for _, lab in MODELS], fontsize=9)
    ax.set_ylabel("capture@5%\n(上位 5% のセルに入った、通報のあったセルの割合)", fontsize=9)
    ax.set_ylim(0, 0.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.set_title("予測より後の年度の通報を、上位 5% のセルでどれだけ捉えたか (秋田県、100 m セル 1,168,211)", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{out}/capture-by-model.png", dpi=150)
    plt.close(fig)

    share, cells = edge_matrix(pd.read_csv(f"{out}/rates_2025_by_edge_building.csv"))
    fig, ax = plt.subplots(figsize=(11, 4.6))
    im = ax.imshow(share.to_numpy() * 100, cmap="OrRd", aspect="auto")
    for i in range(share.shape[0]):
        for j in range(share.shape[1]):
            v = share.iat[i, j] * 100
            ax.text(j, i, f"{v:.2f}%\n{cells.iat[i, j]:,}", ha="center", va="center", fontsize=7,
                    color="white" if v > 5 else "#222222")
    ax.set_xticks(range(len(EDGE)), [e.replace(" ", "\n", 1) for e in EDGE], fontsize=8)
    ax.set_yticks(range(len(share.index)), list(share.index[:-1]) + ["建物を問わない"], fontsize=8)
    ax.axhline(len(BUILDING) - 0.5, color="white", lw=3)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label("2025 年度に通報のあったセルの割合 (%)", fontsize=8)
    ax.set_title("森の縁と建物からの距離ごとの、通報のあったセルの割合 (秋田県 2025 年度。下の数はセル数)", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{out}/rate-by-edge-building.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()

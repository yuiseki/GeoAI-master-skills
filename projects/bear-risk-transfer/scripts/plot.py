"""Bar chart of capture@5% per region for the planned comparison (AK, B_pop, LOCAL), read from the scores files.

Usage:
    uvx --with matplotlib --with numpy python plot.py OUTPUTS_DIR
"""

import json
import sys

import numpy as np


def values(out, regions, models):
    return {r: [json.load(open(f"{out}/{r}_scores.json"))["maps"][m]["capture@0.05"] for m in models] for r in regions}


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = sys.argv[1]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    regions = ["gifu", "kyoto", "ishikawa", "nagaoka"]
    labels = {"gifu": "岐阜県", "kyoto": "京都府", "ishikawa": "石川県", "nagaoka": "長岡市"}
    models = [("AK", "秋田のモデル (そのまま)", "#c4512a"), ("LOCAL", "その地域で学習 (参考)", "#3b6e8f"), ("B_pop", "人口の順位", "#9a9a9a")]
    v = values(out, regions, [m for m, _, _ in models])
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    x = np.arange(len(regions))
    w = 0.26
    for k, (m, name, col) in enumerate(models):
        ax.bar(x + (k - 1) * w, [v[r][k] for r in regions], w, label=name, color=col)
    ax.axhline(0.05, color="#444444", lw=1, ls="--")
    ax.text(len(regions) - 0.5, 0.06, "でたらめ (0.05)", ha="right", fontsize=8, color="#444444")
    ax.set_xticks(x)
    ax.set_xticklabels([labels[r] for r in regions])
    ax.set_ylabel("上位 5% のセルに入った\n目撃のあったセルの割合")
    ax.set_ylim(0, 0.75)
    ax.set_title("秋田で学習したモデルを、ほかの地域へそのまま当てはめた結果 (100 m セル)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{out}/transfer-capture.png", dpi=150)
    json.dump(v, open(f"{out}/transfer-capture.json", "w"), indent=1)


if __name__ == "__main__":
    main()

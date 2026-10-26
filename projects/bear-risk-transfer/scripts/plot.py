"""Bar charts of capture@5% per region: the planned comparison (AK, B_pop, LOCAL) from the scores files, and the
exploration on the later half of the reports (AK, AK restricted to the range, the same without the building features,
and the density of the earlier half) from the e3 files; and OSM buildings per household per region.

Usage:
    uvx --with matplotlib --with numpy python plot.py OUTPUTS_DIR
"""

import json
import sys

import numpy as np


def values(out, regions, models):
    return {r: [json.load(open(f"{out}/{r}_scores.json"))["maps"][m]["capture@0.05"] for m in models] for r in regions}


def explored(out, regions, maps):
    """{region: [capture@5% of each map]} on the later half, from <region>_e3.json."""
    v = {}
    for r in regions:
        d = json.load(open(f"{out}/{r}_e3.json"))["maps"]
        missing = [m for m in maps if m not in d]
        if missing:
            raise SystemExit(f"{r}: no {missing} in {r}_e3.json")
        v[r] = [d[m]["capture@0.05"] for m in maps]
    return v


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
    plt.close(fig)

    regions3 = ["gifu", "kyoto", "ishikawa"]
    maps = [("AK", "秋田のモデル", "#e8a487"), ("AK_range", "分布域で絞る", "#c4512a"),
            ("AK_nobldg_range", "建物を外し、分布域で絞る", "#7a2510"), ("H1", "前半の通報の密度", "#3b6e8f")]
    v = explored(out, regions3, [m for m, _, _ in maps])
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    x = np.arange(len(regions3))
    w = 0.2
    for k, (m, name, col) in enumerate(maps):
        bars = ax.bar(x + (k - 1.5) * w, [v[r][k] for r in regions3], w, label=name, color=col)
        ax.bar_label(bars, labels=[f"{v[r][k]:.3f}" for r in regions3], fontsize=7, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels([labels[r] for r in regions3])
    ax.set_ylabel("上位 5% のセルに入った\n後半の目撃のあったセルの割合")
    ax.set_ylim(0, 0.6)
    ax.set_title("探索: 期間の後半の通報で、秋田のモデルの直し方を比べる (前半の通報で分布域を決めた)", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{out}/explore-later-half.png", dpi=150)
    plt.close(fig)

    import pandas as pd

    b = pd.read_csv(f"{out}/osm_buildings_per_household.csv")
    names = {**labels, "akita": "秋田県"}
    fig, ax = plt.subplots(figsize=(7, 3.2))
    bars = ax.barh([names[r] for r in b.region][::-1], b.ratio[::-1], color=["#9a9a9a"] * (len(b) - 1) + ["#c4512a"])
    ax.bar_label(bars, labels=[f"{r:.3f}" for r in b.ratio[::-1]], fontsize=8, padding=2)
    ax.set_xlabel("OSM の建物の数 / 2020 年国勢調査の世帯数")
    ax.set_xlim(0, 1.9)
    ax.set_title("OSM の建物の描き込みの濃さ (学習に使った秋田は赤)", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{out}/osm-buildings-per-household.png", dpi=150)


if __name__ == "__main__":
    main()

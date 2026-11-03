"""Figures: outputs/site_series.png, outputs/tile_ranking.png, outputs/capture_curve.png.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with matplotlib python scripts/05_fig.py
"""
import csv
import datetime as dt
import json
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from common import ART, OUT, ROOT, TX, TY  # noqa: E402

sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

SOURCE = ("Contains modified Copernicus Sentinel data 2017-2026 (Planetary Computer sentinel-1-rtc, sentinel-2-l2a)。"
          "国土地理院 年度別空中写真 (2019、2024 年度) を見比べた正解、ESA WorldCover 2021、"
          "© OpenStreetMap contributors (ODbL) を加工して作成")
LABEL_COLORS = {"0": "#e6e6e6", "1": "#f2c14e", "2": "#d1495b", "NA": "#ffffff"}


def d(s):
    return dt.date.fromisoformat(s)


def main():
    blocks = json.loads((OUT / "blocks.json").read_text(encoding="utf-8"))
    s2b = json.loads((OUT / "s2_break.json").read_text(encoding="utf-8"))
    with open(OUT / "site_series.csv", encoding="utf-8") as f:
        ss = list(csv.DictReader(f))
    with open(OUT / "s2_series.csv", encoding="utf-8") as f:
        s2 = list(csv.DictReader(f))
    with open(OUT / "tiles.csv", encoding="utf-8") as f:
        tiles = {r["tile"]: r for r in csv.DictReader(f)}
    labels = {}
    with open(OUT.parent / "labels/labels.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            labels[f"{r['tile_x']}_{r['tile_y']}"] = r["label"]

    t1 = "SITE (工事区域の輪郭の中) と CTRL (変わらなかった近くの市街地) の平均の明るさ、Sentinel-1 軌道 46"
    t2 = "SITE の画素のうち、その撮影日に暗くなる変化点が出た割合"
    t3 = "Sentinel-2 の SITE の平均の反射率"
    lab = ["SITE VV", "SITE VH", "CTRL VV", "CTRL VH", "期間 W", "D_sar (中央値)", "D_opt", "dB", "割合", "反射率", "SITE", "CTRL"]
    use_cjk_font(t1 + t2 + t3 + "".join(lab) + SOURCE + "0123456789-")
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    x = [d(r["date"]) for r in ss]
    for col, c, ls, name in (("site_vv_db", "#d1495b", "-", "SITE VV"), ("site_vh_db", "#d1495b", ":", "SITE VH"),
                             ("ctrl_vv_db", "#2e86ab", "-", "CTRL VV"), ("ctrl_vh_db", "#2e86ab", ":", "CTRL VH")):
        axes[0].plot(x, [float(r[col]) for r in ss], ls, color=c, lw=1, label=name)
    axes[0].set_ylabel("dB")
    axes[0].set_title(t1, fontsize=9)
    axes[1].bar(x, [float(r["site_dark_share"]) for r in ss], width=8, color="#d1495b", label="SITE")
    axes[1].bar(x, [-float(r["ctrl_dark_share"]) for r in ss], width=8, color="#2e86ab", label="CTRL")
    axes[1].set_ylabel("割合 (CTRL は下向き)")
    axes[1].set_title(t2, fontsize=9)
    xs2 = [d(r["date"]) for r in s2]
    for b, c in (("B02", "#2e86ab"), ("B04", "#d1495b"), ("B08", "#6a994e"), ("B11", "#8e6c8a")):
        axes[2].plot(xs2, [float(r[b]) for r in s2], ".-", ms=2, lw=0.5, color=c, label=b)
    axes[2].set_ylabel("反射率")
    axes[2].set_title(t3, fontsize=9)
    for ax in axes:
        ax.axvspan(d(blocks["settings"]["W"][0]), d(blocks["settings"]["W"][1]), color="#f2c14e", alpha=0.12,
                   label="期間 W" if ax is axes[0] else None)
        if blocks["A"]["D_sar"]:
            ax.axvline(d(blocks["A"]["D_sar"]), color="black", lw=1, label="D_sar (中央値)" if ax is axes[0] else None)
        ax.axvline(d(s2b["D_opt"]), color="black", lw=1, ls="--", label="D_opt" if ax is axes[0] else None)
        ax.legend(fontsize=7, loc="upper left", ncol=4)
    fig.text(0.01, 0.005, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT / "site_series.png", dpi=130)
    plt.close(fig)

    tt = ["SAR の点数 (2019 年度と 2024 年度の平均の差が 3 dB 以上の画素の割合)", "写真の見比べの正解",
          "画素の 2019 年度と 2024 年度の差 (dB、VV と VH の大きい方)"]
    use_cjk_font("".join(tt) + "上位 24 枚多数少し変化なし欠け調べる場所" + SOURCE + "0123456789%.")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.6))
    xs, ys = list(TX), list(TY)
    sc = np.full((12, 12), np.nan)
    for i, tx in enumerate(xs):
        for j, ty in enumerate(ys):
            k = f"{tx}_{ty}"
            if k in tiles:
                sc[j, i] = float(tiles[k]["score_db3"])
    im = axes[0].imshow(sc, cmap="viridis", vmin=0)
    plt.colorbar(im, ax=axes[0], fraction=0.046)
    top = {k for k, r in tiles.items() if int(r["rank_db3"]) <= blocks["B"]["k"]}
    for i, tx in enumerate(xs):
        for j, ty in enumerate(ys):
            k = f"{tx}_{ty}"
            axes[1].add_patch(Rectangle((i - 0.5, j - 0.5), 1, 1, color=LABEL_COLORS[labels[k]]))
            if k in top:
                for ax in axes[:2]:
                    ax.add_patch(Rectangle((i - 0.45, j - 0.45), 0.9, 0.9, fill=False, ec="black", lw=1.5))
            if k == blocks.get("site_tile", "58289_25820"):
                for ax in axes[:2]:
                    ax.plot(i, j, "o", mfc="none", mec="white" if ax is axes[0] else "black", ms=14, mew=2)
    axes[1].set_xlim(-0.5, 11.5)
    axes[1].set_ylim(11.5, -0.5)
    axes[1].set_aspect("equal")
    from matplotlib.patches import Patch
    axes[1].legend(handles=[Patch(color=LABEL_COLORS["2"], label="2 多数の変化"), Patch(color=LABEL_COLORS["1"], label="1 少し"),
                            Patch(color=LABEL_COLORS["0"], label="0 変化なし"),
                            Patch(fc="white", ec="grey", label="欠け (写真が片方の年に無い)"),
                            Patch(fc="none", ec="black", label="SAR の上位 24 枚")],
                   fontsize=7, loc="lower left", bbox_to_anchor=(0, -0.22), ncol=3)
    for ax, t in zip(axes[:2], tt[:2]):
        ax.set_title(t + "\n丸が調べる場所のタイル", fontsize=9)
        ax.set_xticks(range(12))
        ax.set_xticklabels([str(v)[-2:] for v in xs], fontsize=6)
        ax.set_yticks(range(12))
        ax.set_yticklabels([str(v)[-2:] for v in ys], fontsize=6)
    z = np.load(ART / "fy_ddb.npz")
    ddb = np.where(z["valid"], z["ddb"].max(0), np.nan)
    im = axes[2].imshow(ddb, cmap="magma", vmin=0, vmax=8, interpolation="nearest")
    plt.colorbar(im, ax=axes[2], fraction=0.046)
    axes[2].set_title(tt[2] + "\n範囲はタイル 144 枚の外接の箱 (UTM、北が上)", fontsize=9)
    axes[2].set_xticks([])
    axes[2].set_yticks([])
    fig.text(0.01, 0.01, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "tile_ranking.png", dpi=120)
    plt.close(fig)

    cc = blocks["B_capture_curve"]
    n = len(cc["sar"]) - 1
    t4 = "買うタイルの枚数と、拾える「多数の変化」のタイルの数"
    use_cjk_font(t4 + "SAR の点数の順市街地の割合の順無作為 (期待値)買うタイルの割合拾えた割合上位 20 %" + SOURCE + "0123456789%")
    fig, ax = plt.subplots(figsize=(7, 5.5))
    k = np.arange(n + 1) / n
    ax.plot(k, np.array(cc["sar"]) / cc["positives_2"], color="#d1495b", label="SAR の点数の順")
    ax.plot(k, np.array(cc["builtup"]) / cc["positives_2"], color="#2e86ab", label="市街地の割合の順")
    ax.plot([0, 1], [0, 1], color="grey", ls=":", label="無作為 (期待値)")
    ax.axvline(0.2, color="black", lw=0.6, ls="--")
    ax.text(0.205, 0.03, "上位 20 %", fontsize=8)
    ax.set_xlabel("買うタイルの割合 (120 枚のうち)")
    ax.set_ylabel(f"拾えた割合 (正解 2 の {cc['positives_2']} 枚のうち)")
    ax.set_title(t4, fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    fig.text(0.01, 0.005, SOURCE, fontsize=5, wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "capture_curve.png", dpi=130)
    plt.close(fig)
    (OUT / "figure_sources.txt").write_text(SOURCE + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

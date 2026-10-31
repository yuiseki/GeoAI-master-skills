"""Figures of stage B.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with pyproj --with matplotlib python scripts/12_fig_b.py

- outputs/polder_surface.png: the polder's water surface by date (GSI read here, the article's values, and the
  satellite surfaces: the planned 99 % point, the same with DEM5A only, and the 10-01 and 10-06 ones), and the
  09-24 detection rate by GSI depth band (here and in the article).
- outputs/depth_0924.png: the GSI depth of 09-24 14:00 and the satellite depth of 09-24 17:41 (planned rule and
  DEM5A only) over the box around the comparison window.
"""
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

dp = __import__("11_depth")
fb = dp.fb
OUT = HERE.parent / "outputs"
SOURCE = ("Contains modified Copernicus Sentinel data 2026 (Planetary Computer sentinel-1-grd)。\n"
          "国土地理院「浸水推定図『北印旛沼』」の深さのタイルと PDF の凡例、DEM5A、DEM10B を加工して作成")
ARTICLE_RATE = [0.39, 0.58, 0.76, 0.90]


def main():
    labels = ["推定図 (ここで読んだ値)", "記事 2 の推定図の値", "衛星 (計画: 99 % 点)", "衛星 (DEM5A だけ)",
              "衛星 (10/01、10/06)", "水面の標高 (m)", "深さの帯 (m)", "衛星が水とした割合", "この追試", "記事 2 (90 % 以上)",
              "推定図 9/24 14 時の深さ", "衛星 9/24 17:41 の深さ (計画)", "衛星の深さ (DEM5A だけ)", "深さ (m)", "月/日"]
    use_cjk_font("".join(labels) + SOURCE + " (3 以上は同じ色)。灰色はもともとの水面〜0123456789./−")
    b = json.loads((OUT / "blocks_b.json").read_text(encoding="utf-8"))["main"]
    x5 = json.loads((OUT / "explore_b.json").read_text(encoding="utf-8"))["dem5a_only"]
    t0 = dp.T["0922"]
    day = lambda k: (dp.T[k] - t0).total_seconds() / 86400 + 22  # noqa: E731  (days of September)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.6, 1]})
    vs = fb.VERSIONS
    ax.plot([day(v) for v in vs], [b["polder"]["gsi_surface_m"][v] for v in vs], "o-", color="#1f3a68", label=labels[0])
    ax.plot([day(v) for v in vs], [dp.ARTICLE[v] for v in vs], "s--", color="#888888", label=labels[1])
    ax.plot([day("s0924")], [b["polder"]["sat_surface_m"]["0924"]], "^", color="#d62728", ms=9, label=labels[2])
    ax.plot([day("s0924")], [x5["polder"]["sat_surface_m"]["0924"]], "v", color="#e6b800", ms=9, label=labels[3])
    ax.plot([day("s1001"), day("s1006")], [b["polder"]["sat_surface_m"]["1001"], b["polder"]["sat_surface_m"]["1006"]], "D",
            color="#2ca02c", label=labels[4])
    ax.set_ylabel(labels[5])
    ticks = [22, 24, 26, 28, 30, 32, 34, 36]
    ax.set_xticks(ticks, [f"9/{t}" if t <= 30 else f"10/{t - 30}" for t in ticks])
    ax.set_xlabel(labels[14])
    ax.legend(fontsize=8)
    bands = list(b["E3"])
    xs = np.arange(len(bands))
    ax2.bar(xs - 0.2, [b["E3"][k]["rate"] for k in bands], 0.4, color="#1f3a68", label=labels[8])
    ax2.bar(xs + 0.2, ARTICLE_RATE, 0.4, color="#bbbbbb", label=labels[9])
    ax2.set_xticks(xs, ["0〜0.25", "0.25〜0.5", "0.5〜0.75", "0.75〜"])
    ax2.set_xlabel(labels[6])
    ax2.set_ylabel(labels[7])
    ax2.set_ylim(0, 1)
    ax2.legend(fontsize=8)
    fig.text(0.01, 0.005, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUT / "polder_surface.png", dpi=150)
    plt.close(fig)

    g = dict(np.load(fb.ART / "grid.npz"))
    gsi = np.load(fb.ART / "gsi_depth.npz")["depth_0924"]
    sat = np.load(fb.ART / "depth_b.npz")["sat_0924"]
    g5 = {**g, "dem": np.where(g["dem_src"] == 1, g["dem"], np.nan)}
    w = dict(np.load(fb.ART / "water_b.npz"))
    mask = w["w0924"] & ~g["water"]
    lab = dp.parts(mask, 100)
    sat5 = dp.depth_from_surfaces(lab, dp.surfaces(lab, mask, g5["dem"], "quantile"), g5["dem"])
    win = np.load(fb.ART / "windows.npz")["buffer"]
    rows, cols = np.where(win)
    rs, cs = slice(rows.min(), rows.max() + 1), slice(cols.min(), cols.max() + 1)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4), sharey=True)
    for ax, img, title in zip(axes, (gsi, sat, sat5), labels[10:13]):
        bg = np.where(g["water"][rs, cs], 0.5, np.nan)
        ax.imshow(bg, cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
        im = ax.imshow(img[rs, cs], cmap="Blues", vmin=0, vmax=3, interpolation="nearest")
        ax.set_title(title, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(im, ax=axes, shrink=0.7, label=labels[13] + " (3 以上は同じ色)")
    fig.text(0.01, -0.04, SOURCE + "。灰色はもともとの水面", fontsize=6)
    fig.savefig(OUT / "depth_0924.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    (OUT / "figure_sources_b.txt").write_text(SOURCE + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

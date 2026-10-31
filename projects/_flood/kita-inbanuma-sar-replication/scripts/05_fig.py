"""Figures of stage A.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with shapely --with matplotlib python scripts/05_fig.py

- outputs/composite.png: VV before (red) and after (green and blue), over the box around the comparison window.
  Red is where the ground got darker after the rain.
- outputs/compare.png: the VV detection and the VV + VH detection against the GSI outline of 09-24 14:00, over the
  same box: both, outline only (missed), detection only (extra), permanent water. The comparison window is outlined.
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

detect_mod = __import__("03_detect")
OUT = HERE.parent / "outputs"
SOURCE = ("Contains modified Copernicus Sentinel data 2026 (Planetary Computer sentinel-1-rtc)。\n"
          "国土地理院「浸水推定図『北印旛沼』」の輪郭線、DEM5A、ESA WorldCover 2021 を加工して作成")
LABELS = ["両方で浸水", "推定図だけ (見逃し)", "判定だけ", "もともとの水面", "比較範囲"]


def crop_box(win, pad=30):
    rows, cols = np.where(win)
    return slice(max(rows.min() - pad, 0), rows.max() + pad), slice(max(cols.min() - pad, 0), cols.max() + pad)


def scale(db, lo=-25, hi=0):
    return np.clip((db - lo) / (hi - lo), 0, 1)


def extent(transform, rs, cs):
    a, _, c, _, e, f = transform
    x0, y0 = c + cs.start * a, f + rs.start * e
    return [(x0 - c) / 1000, (x0 + (cs.stop - cs.start) * a - c) / 1000,
            (y0 + (rs.stop - rs.start) * e - f) / 1000, (y0 - f) / 1000]


def main():
    title1 = "Sentinel-1 VV の前後 (赤: 9/12、緑と青: 9/24 17:41)。赤いほど大雨の後に暗くなった"
    title2 = ["VV だけの判定", "VV と VH の判定"]
    use_cjk_font(title1 + "".join(title2) + "".join(LABELS) + SOURCE + "東西 km 南北 0123456789−")
    g = detect_mod.load_grid()
    win = np.load(detect_mod.ART / "windows.npz")["buffer"]
    d = np.load(detect_mod.ART / "detect_plan.npz")
    rs, cs = crop_box(win)
    ext = extent(g["transform"], rs, cs)

    rgb = np.dstack([scale(g["vv_b"][rs, cs]), scale(g["vv_a"][rs, cs]), scale(g["vv_a"][rs, cs])])
    fig, ax = plt.subplots(figsize=(7, 8.5))
    ax.imshow(rgb, extent=ext, interpolation="nearest")
    ax.contour(np.linspace(ext[0], ext[1], cs.stop - cs.start), np.linspace(ext[3], ext[2], rs.stop - rs.start),
               g["ref_0924"][rs, cs].astype(float), levels=[0.5], colors="yellow", linewidths=0.6)
    ax.set_title(title1, fontsize=9)
    ax.set_xlabel("東西 km (格子の西端から)")
    ax.set_ylabel("南北 km (格子の北端から)")
    fig.text(0.01, 0.005, SOURCE + "。黄の線は推定図 9/24 14 時", fontsize=6)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "composite.png", dpi=150)
    plt.close(fig)

    cmap = ListedColormap(["#f2f2f2", "#2ca02c", "#e6b800", "#d62728", "#1f3a68"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 7.5), sharey=True)
    ref, water = g["ref_0924"], g["water"]
    for ax, key, title in zip(axes, ("det_vv", "det_vvvh"), title2):
        det = d[key]
        c = np.zeros(ref.shape, np.uint8)
        c[ref & det] = 1
        c[ref & ~det] = 2
        c[~ref & det] = 3
        c[water] = 4
        ax.imshow(c[rs, cs], cmap=cmap, vmin=0, vmax=4, extent=ext, interpolation="nearest")
        ax.contour(np.linspace(ext[0], ext[1], cs.stop - cs.start), np.linspace(ext[3], ext[2], rs.stop - rs.start),
                   win[rs, cs].astype(float), levels=[0.5], colors="black", linewidths=0.6, linestyles="dashed")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("東西 km (格子の西端から)")
    axes[0].set_ylabel("南北 km (格子の北端から)")
    handles = [Patch(color=cmap(i), label=l) for i, l in zip(range(1, 5), LABELS[:4])]
    handles.append(Patch(facecolor="none", edgecolor="black", linestyle="dashed", label=LABELS[4]))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8, bbox_to_anchor=(0.5, 0.04))
    fig.text(0.01, 0.005, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.09, 1, 0.97))
    fig.savefig(OUT / "compare.png", dpi=150)
    plt.close(fig)
    (OUT / "figure_sources.txt").write_text(SOURCE + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

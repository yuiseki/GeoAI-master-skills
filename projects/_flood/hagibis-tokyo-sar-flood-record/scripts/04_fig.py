"""Figures: outputs/delta_map.png (dVV of orbit 46 over the box and three close-ups with the record outlines, the
channel zone and A31a) and outputs/rates.png (the rates of B0 to B2 for both orbits). Source line in figure_sources.txt.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with matplotlib --with shapely --with pyproj python scripts/04_fig.py
"""
import json
import sys

import matplotlib
import numpy as np
import shapely
from pyproj import Transformer

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import ART, OUT, RAW, ROOT, UTM  # noqa: E402

sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

SOURCE = ("Contains modified Copernicus Sentinel data 2019 (Planetary Computer sentinel-1-rtc)。東京都「水害リスク情報システム 浸水実績図データ」、"
          "国土交通省 国土数値情報 (洪水浸水想定区域 A31a、行政区域 N03)、ESA WorldCover 2021、© OpenStreetMap contributors (ODbL) を加工して作成")
ZOOMS = [("狛江市・調布市", (139.545, 35.615, 139.600, 35.648)), ("世田谷区玉川・大田区田園調布", (139.622, 35.585, 139.672, 35.615)),
         ("日野市・八王子市", (139.395, 35.650, 139.445, 35.675))]
TO_UTM = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)


def rec_rings():
    fc = json.loads((RAW / "vectors/rec_2019.geojson").read_text(encoding="utf-8"))
    gs = shapely.from_geojson([json.dumps(f["geometry"]) for f in fc["features"]])
    gs = shapely.transform(gs, lambda xy: np.column_stack(TO_UTM.transform(xy[:, 0], xy[:, 1])))
    rings = []
    for g in gs:
        for p in getattr(g, "geoms", [g]):
            rings.append(np.asarray(p.exterior.coords))
    return rings


def main():
    aux = np.load(ART / "aux.npz")
    t = aux["transform"]
    rows, cols = aux["wc"].shape
    ext = (t[2], t[2] + cols * t[0], t[5] + rows * t[4], t[5])
    d = np.load(ART / "delta_o46.npz")["dvv"]
    tokyo = aux["tokyo"] & (aux["wc"] != 80)
    show = np.where(tokyo, d, np.nan)
    chan = (aux["dist_tama"] <= 300) & ~aux["a31a"] & aux["tokyo"]
    rings = rec_rings()
    blocks = json.loads((OUT / "blocks.json").read_text(encoding="utf-8"))

    labels = ["全体", "雨の後と前の VV の差 (dB)", "記録の面", "河道 (CHANNEL)", "A31a 想定最大規模", "東京都の外と恒常的な水は灰色"]
    use_cjk_font("".join(labels) + "".join(z[0] for z in ZOOMS) + SOURCE + "0123456789-+.()、。拡大図だけ")
    fig = plt.figure(figsize=(16, 13))
    ax0 = fig.add_axes([0.03, 0.47, 0.88, 0.50])
    axz = [fig.add_axes([0.03 + i * 0.325, 0.05, 0.30, 0.38]) for i in range(3)]
    cm = plt.get_cmap("RdBu").copy()
    cm.set_bad("#d9d9d9")
    zooms = [(f"{i + 1}. {n}", bb) for i, (n, bb) in enumerate(ZOOMS)]
    for ax, (title, bb) in [(ax0, ("全体 (軌道 46、2019-10-13 05:43 と雨の前 6 回の平均の差)", None))] + list(zip(axz, zooms)):
        im = ax.imshow(show, extent=ext, cmap=cm, vmin=-8, vmax=8, interpolation="nearest")
        if bb:  # the A31a borders are too dense to read on the whole box
            ax.contour(np.flipud(aux["a31a"].astype(float)), levels=[0.5], extent=ext, colors="#6a3d9a", linewidths=0.4,
                       origin="lower")
        ax.contour(np.flipud(chan.astype(float)), levels=[0.5], extent=ext, colors="#1b9e77", linewidths=0.6, origin="lower")
        for r in rings:
            ax.plot(r[:, 0], r[:, 1], color="black", lw=0.8 if bb else 1.2)
        if bb:
            xs, ys = TO_UTM.transform([bb[0], bb[2]], [bb[1], bb[3]])
            ax.set_xlim(xs)
            ax.set_ylim(ys)
            ax0.add_patch(plt.Rectangle((xs[0], ys[0]), xs[1] - xs[0], ys[1] - ys[0], fill=False, ec="black", lw=1, ls="--"))
            ax0.text(xs[0], ys[1], title.split(".")[0], fontsize=11, va="bottom", fontweight="bold")
        ax.set_title(title, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    cb = fig.colorbar(im, ax=ax0, fraction=0.02, pad=0.01)
    cb.set_label("雨の後と前の VV の差 (dB)")
    from matplotlib.lines import Line2D
    ax0.legend(handles=[Line2D([], [], color="black", label="記録の面 (2019 年、85 面)"),
                        Line2D([], [], color="#1b9e77", label="河道 (CHANNEL、多摩川の中心線から 300 m、A31a の外)"),
                        Line2D([], [], color="#6a3d9a", label="A31a 想定最大規模の区域の境 (拡大図だけ)"),
                        Line2D([], [], color="#d9d9d9", lw=6, label="東京都の外と恒常的な水は灰色")],
               fontsize=8, loc="lower left")
    fig.text(0.01, 0.01, SOURCE, fontsize=7)
    fig.savefig(OUT / "delta_map.png", dpi=110)
    plt.close(fig)

    t2 = "暗くなった画素の割合 (B0、B1) と、市街地で明るくなった画素の割合 (B2)"
    names = ["河道", "記録の面", "記録の面の市街地", "対照 (標準化)", "軌道 46 (10-13 05:43、雨の後)", "軌道 39 (10-12 17:41、雨の最中)", "割合", "暗くなった", "明るくなった"]
    use_cjk_font(t2 + "".join(names) + SOURCE + "0123456789%.")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, o, ttl in zip(axes, ("o46", "o39"), names[4:6]):
        m = blocks[o]
        bars = [("河道\n暗くなった", m["B0"]), ("記録の面\n暗くなった", m["B1"]), ("記録の面の市街地\n明るくなった", m["B2"])]
        for i, (lab, b) in enumerate(bars):
            for j, (key, ci, c) in enumerate((("p_target", "p_target_ci", "#d1495b"), ("p_ref_std", "p_ref_std_ci", "#2e86ab"))):
                v, (lo, hi) = b[key], b[ci]
                ax.bar(i + (j - 0.5) * 0.38, v, width=0.36, color=c, label=(["対象の組", "対照 (標準化)"][j] if i == 0 else None))
                ax.errorbar(i + (j - 0.5) * 0.38, v, yerr=[[v - lo], [hi - v]], color="black", capsize=3, lw=1)
        ax.set_xticks(range(3))
        ax.set_xticklabels([b[0] for b in bars], fontsize=9)
        ax.set_title(ttl, fontsize=10)
        ax.set_ylabel("割合")
        ax.legend(fontsize=8)
    fig.suptitle(t2, fontsize=11)
    fig.text(0.01, 0.01, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(OUT / "rates.png", dpi=130)
    plt.close(fig)
    (OUT / "figure_sources.txt").write_text(SOURCE + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

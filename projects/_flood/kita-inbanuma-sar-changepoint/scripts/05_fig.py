"""Figures of the main analysis (outputs/changepoint_map.png, outputs/daily_share.png).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with matplotlib python scripts/05_fig.py
"""
import csv
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

ART = ROOT / "artifacts/_flood/kita-inbanuma-sar-changepoint"
OUT = HERE.parent / "outputs"
SOURCE = ("Contains modified Copernicus Sentinel data 2026 (Planetary Computer sentinel-1-rtc)。"
          "国土地理院「浸水推定図『北印旛沼』」の輪郭線、ESA WorldCover 2021 を加工して作成")
GREY, NAVY = "#e6e6e6", "#1f3b63"
PALETTE = ["#9aa9b8", "#c9a227", "#d1495b", "#2e86ab", "#6a994e", "#8e6c8a"]


def first_date_map(change, ratio, dates, window, sign):
    """Index (into window) of the first change of the given sign within the window dates; -1 if none."""
    out = np.full(change.shape[1:], -1, np.int8)
    for k, d in reversed(list(enumerate(window))):
        i = dates.index(d)
        hit = change[i] & ((ratio[i] < 0) if sign < 0 else (ratio[i] > 0))
        out[hit] = k
    return out


def crop(aux):
    m = aux["ref_0922"] | aux["ref_0924"] | aux["ref_0925"] | aux["ref_1001"]
    r, c = np.where(m)
    pad = 150
    return slice(max(r.min() - pad, 0), r.max() + pad), slice(max(c.min() - pad, 0), c.max() + pad)


def panel(ax, code, labels, water, outline, title):
    rgb = np.zeros(code.shape + (3,))
    rgb[:] = matplotlib.colors.to_rgb(GREY)
    for k in range(len(labels)):
        rgb[code == k] = matplotlib.colors.to_rgb(PALETTE[k])
    rgb[water] = matplotlib.colors.to_rgb(NAVY)
    ax.imshow(rgb, interpolation="nearest")
    ax.contour(outline.astype(float), levels=[0.5], colors="black", linewidths=0.6)
    ax.set_title(title, fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
    handles = [Patch(color=PALETTE[k], label=lab) for k, lab in enumerate(labels)]
    handles += [Patch(color=GREY, label="変化点なし"), Patch(color=NAVY, label="もともとの水面")]
    ax.legend(handles=handles, loc="lower left", fontsize=6.5, framealpha=0.9)


def main():
    aux = np.load(ART / "aux.npz")
    rs, cs = crop(aux)
    water = aux["wc"][rs, cs] == 80
    c39 = np.load(ART / "change_o39.npz")
    c141 = np.load(ART / "change_o141.npz")
    d39, d141 = [str(d) for d in c39["dates"]], [str(d) for d in c141["dates"]]
    ch39, r39 = c39["change"][:, rs, cs], c39["ratio_db"][:, rs, cs].astype(float)
    ch141, r141 = c141["change"][:, rs, cs], c141["ratio_db"][:, rs, cs].astype(float)

    w39 = [d for d in d39 if "2026-08-31" <= d <= "2026-10-30"]
    w141 = [d for d in d141 if "2026-09-07" <= d <= "2026-10-25"]
    dark39 = first_date_map(ch39, r39, d39, w39, -1)
    i24 = d39.index("2026-09-24")
    after = [d for d in d39 if d > "2026-09-24"]
    back = first_date_map(ch39, r39, d39, after, +1)
    back[~(ch39[i24] & (r39[i24] < 0))] = -2
    dark141 = first_date_map(ch141, r141, d141, w141, -1)

    lab = lambda ds: [d[5:].replace("-", "/") for d in ds]  # noqa: E731
    t1 = "軌道 39: 最初に暗くなった撮影日 (8/31〜10/30)"
    t2 = "軌道 39: 9/24 に暗くなった所が明るく戻った日"
    t3 = "軌道 141: 最初に暗くなった撮影日 (9/07〜10/25)"
    use_cjk_font(t1 + t2 + t3 + SOURCE + "".join(lab(w39 + after + w141)) + "変化点なしもともとの水面戻らない"
                 "9/24 に暗くならなかった推定図の輪郭線 (黒) 9/24 14 時 10/01 16 時")
    fig, axes = plt.subplots(1, 3, figsize=(15, 6.2))
    panel(axes[0], dark39, lab(w39), water, aux["ref_0924"][rs, cs], t1 + "\n黒の線は推定図 9/24 14 時")
    code = back.copy()
    code[back == -1] = len(after)
    code[back == -2] = -1
    rgb_labels = lab(after) + ["戻らない (10/30 まで)"]
    panel(axes[1], code, rgb_labels, water, aux["ref_1001"][rs, cs], t2 + "\n灰色は 9/24 に暗くならなかった。黒の線は推定図 10/01 16 時")
    panel(axes[2], dark141, lab(w141), water, aux["ref_1001"][rs, cs], t3 + "\n黒の線は推定図 10/01 16 時")
    fig.text(0.01, 0.01, SOURCE, fontsize=6.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "changepoint_map.png", dpi=130)
    plt.close(fig)

    names = {"IN39": "推定図 9/24 の浸水域", "IN141": "推定図 10/01 の浸水域", "RECEDED": "10/01 までに引いた所",
             "CTRL": "浸水しなかった低地の農地", "STABLE": "台地の林"}
    colors = {"IN39": "#d1495b", "IN141": "#d1495b", "RECEDED": "#c9a227", "CTRL": "#2e86ab", "STABLE": "#6a994e"}
    tt = ["軌道 39 (17 枚)", "軌道 141 (20 枚)"]
    ylab = "変化点のある画素の割合 (実線 暗く、破線 明るく)"
    use_cjk_font("".join(names.values()) + "".join(tt) + ylab + SOURCE + "撮影日 α = 0.01 0123456789/")
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharey=True)
    for ax, o, sets, title in zip(axes, (39, 141), (("IN39", "RECEDED", "CTRL", "STABLE"), ("IN141", "CTRL", "STABLE")), tt):
        with open(OUT / f"daily_o{o}.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for s in sets:
            r = [x for x in rows if x["set"] == s][1:]
            x = [x_["date"][5:].replace("-", "/") for x_ in r]
            ax.plot(x, [float(v["dark"]) for v in r], "-o", ms=3, color=colors[s], label=names[s])
            ax.plot(x, [float(v["bright"]) for v in r], "--", color=colors[s], lw=1)
        ax.axhline(0.01, color="black", lw=0.6, ls=":")
        ax.text(0.2, 0.012, "α = 0.01", fontsize=7)
        ax.set_yscale("log")
        ax.set_ylim(1e-3, 1.2)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylab, fontsize=8)
        ax.tick_params(axis="x", labelsize=7, rotation=60)
        ax.legend(fontsize=7, loc="upper left")
    axes[1].set_xlabel("撮影日")
    fig.text(0.01, 0.005, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT / "daily_share.png", dpi=130)
    plt.close(fig)
    (OUT / "figure_sources.txt").write_text(SOURCE + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

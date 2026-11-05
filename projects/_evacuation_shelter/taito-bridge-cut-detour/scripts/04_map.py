"""Map of the worst single-bridge cut increment for Taito-ku origins (main variant).

uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pandas --with pyarrow --with matplotlib \
  python scripts/04_map.py [--variant main]

Question the figure answers: where in Taito-ku does cutting one bridge lengthen the walk to a flood evacuation
site, and which bridge does it? Values come from origins.parquet and structures.csv; nothing is recomputed.
Writes outputs/<variant>/map_increment.png.
"""
import argparse
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.colors import BoundaryNorm, ListedColormap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

ART = ROOT / "artifacts/_evacuation_shelter/taito-bridge-cut-detour"
RAILWAY = ("rail", "light_rail", "monorail", "subway", "narrow_gauge")
BINS = [0, 1, 50, 100, 200, 300]
LABELS = ["伸びない", "1〜50 m", "50〜100 m", "100〜200 m", "200〜300 m"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="main")
    a = ap.parse_args()
    out = HERE.parent / "outputs" / a.variant
    o = pd.read_parquet(ART / a.variant / "origins.parquet")
    o = o[o.used]
    assert np.isfinite(o.inc).all(), "unreachable origins: the bins below do not show them"
    assert o.inc.max() < BINS[-1], o.inc.max()
    st = pd.read_csv(out / "structures.csv")
    raw = ART / "raw_b5000"
    c = duckdb.connect()
    c.execute("load spatial")
    taito = shapely.from_wkb(bytes(c.execute(f"select st_aswkb(g) from '{raw}/taito.parquet'").fetchall()[0][0]))
    q = lambda w: [shapely.from_wkb(bytes(r[0])) for r in c.execute(
        f"select st_aswkb(g) from '{raw}/lines.parquet' where {w}").fetchall()]
    rails = q(f"railway in {RAILWAY} and (tunnel is null or tunnel = 'no')")
    rivers = [shapely.from_wkb(bytes(r[0])) for r in c.execute(f"select st_aswkb(g) from '{raw}/water.parquet'").fetchall()]
    roads = q("highway in ('trunk','primary','secondary','tertiary')")
    sites = c.execute(f"select st_x(g), st_y(g) from '{raw}/sites.parquet' where flood").fetchall()

    named = st.sort_values("inc_sum_m", ascending=False).head(6)
    texts = ["台東区", "避難場所 (洪水)", "線路 (地上)", "水面", "幹線道路", "橋を 1 つ外したときの最大の伸び",
             "出発点", "外すと伸びが最大になる橋"] + LABELS + list(named.name.fillna("")) + ["N", "500 m", "0", "1 km"]
    use_cjk_font(" ".join(texts))

    fig, ax = plt.subplots(figsize=(9, 10))
    x0, y0, x1, y1 = taito.buffer(400).bounds
    view = shapely.box(x0, y0, x1, y1)
    for g in rivers:
        if g.intersects(view):
            for p in getattr(g, "geoms", [g]):
                ax.fill(*p.exterior.xy, color="#bcd7ee", lw=0, zorder=0)
    for g in roads:
        if g.intersects(view):
            for p in getattr(g, "geoms", [g]):
                ax.plot(*p.xy, color="#d9d9d9", lw=0.8, zorder=1)
    for g in rails:
        if g.intersects(view):
            for p in getattr(g, "geoms", [g]):
                ax.plot(*p.xy, color="#555555", lw=1.0, zorder=2)
    for p in getattr(taito, "geoms", [taito]):
        ax.plot(*p.exterior.xy, color="black", lw=1.2, zorder=3)

    colors = ["#e8e8e8", "#fde0a0", "#f9a65a", "#e2533a", "#8f1d1d"]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(BINS, cmap.N)
    zero = o.inc <= 0
    ax.scatter(o.x[zero], o.y[zero], s=4, c=colors[0], marker="s", lw=0, zorder=4)
    sc = ax.scatter(o.x[~zero], o.y[~zero], s=9, c=o.inc[~zero], cmap=cmap, norm=norm, marker="s", lw=0, zorder=5)
    sx, sy = np.array(sites).T
    inside = [view.contains(shapely.Point(x, y)) for x, y in sites]
    ax.scatter(sx[inside], sy[inside], s=40, marker="^", facecolor="#1f6fb2", edgecolor="white", lw=0.8, zorder=6,
               label="避難場所 (洪水)")

    # label the structures that give the largest summed increments, at their centroid (from structures.csv)
    from pyproj import Transformer
    to_xy = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
    for r in named.itertuples():
        px, py = to_xy.transform(r.lon, r.lat)
        ax.scatter([px], [py], s=60, marker="o", facecolor="none", edgecolor="black", lw=1.2, zorder=7)
        if isinstance(r.name, str) and r.name:
            ax.annotate(r.name, (px, py), xytext=(6, 6), textcoords="offset points", fontsize=8, zorder=8,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))

    cb = fig.colorbar(sc, ax=ax, shrink=0.5, ticks=[0.5, 25, 75, 150, 250])
    cb.ax.set_yticklabels(LABELS)
    cb.set_label("橋を 1 つ外したときの最大の伸び")
    ax.plot([], [], color="#555555", label="線路 (地上)")
    ax.scatter([], [], s=60, marker="o", facecolor="none", edgecolor="black", label="外すと伸びが最大になる橋")
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.plot([x1 - 1300, x1 - 300], [y0 + 200, y0 + 200], color="black", lw=2)
    ax.text(x1 - 800, y0 + 260, "1 km", ha="center", fontsize=8)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    n = len(o)
    ax.set_title(f"台東区: 橋を 1 つ外したときの、洪水の避難場所までの道のりの最大の伸び\n"
                 f"出発点 {n:,} (50 m 間隔)、{a.variant}", fontsize=11)
    ax.text(0.0, -0.02, "EPSG:6677。OSM 2026-08-31 (ODbL)、国土地理院 指定緊急避難場所 2026-10-06 取得、"
             "国勢調査 2020 境界。加工して作成", fontsize=7, transform=ax.transAxes, va="top")
    fig.savefig(out / "map_increment.png", dpi=150, bbox_inches="tight")
    print(out / "map_increment.png")


if __name__ == "__main__":
    main()

"""Map of the 23 wards: the OSM underpass units (listed or not on the national list, in a flood record area or not)
and the list points with no unit within 100 m.

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with shapely --with matplotlib python scripts/03_fig.py

Writes outputs/map_listing.png and outputs/figure_sources.txt.
"""
import sys
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/tokyo23-underpass-listing"
RAW = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a/raw"
OUT = HERE.parent / "outputs"
LIST = "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet"
SOURCE = ("© OpenStreetMap contributors (ODbL)。「全国のアンダーパス箇所マップ」(国土交通省)、東京都「浸水実績図」、\n"
          "国勢調査の境界 (jp-admin-2026-09) をもとに作成")
LABELS = ["一覧に載る (100 m 以内)", "一覧に載らない", "浸水実績の区域に入る (塗りつぶし)", "一覧の点で、近くに OSM の区域が無いもの",
          "OSM のタグから作った 23 区のアンダーパスと国の一覧", "東西 km", "南北 km"]


def main():
    use_cjk_font("".join(LABELS) + SOURCE + "0123456789−")
    c = duckdb.connect()
    c.execute("load spatial")
    wards = c.execute(f"""select st_aswkb(st_transform(geometry, 'EPSG:4612', 'EPSG:6677', always_xy := true))
        from '{RAW / 'wards.parquet'}'""").fetchall()
    import shapely
    wg = [shapely.from_wkb(bytes(w[0])) for w in wards]
    u = pd.read_parquet(ART / "units_main.parquet")
    miss = pd.read_csv(ART / "unmatched_list_points.csv")
    pts = c.execute(f"""select id, st_x(p), st_y(p) from (select id, st_transform(st_point(lon, lat), 'OGC:CRS84', 'EPSG:6677', always_xy := true) p
        from '{LIST}')""").fetchall()
    loc = {i: (x, y) for i, x, y in pts}
    fig, ax = plt.subplots(figsize=(9, 9))
    for g in wg:
        for poly in getattr(g, "geoms", [g]):
            xs, ys = poly.exterior.xy
            ax.plot(np.array(xs) / 1000, np.array(ys) / 1000, color="#bbbbbb", lw=0.5)
    listed = u["d_list"] <= 100
    for m, color, label in ((listed, "#d62728", LABELS[0]), (~listed, "#1f3a68", LABELS[1])):
        sub = u[m]
        ax.scatter(sub["x"] / 1000, sub["y"] / 1000, s=np.where(sub["flood"], 46, 22), facecolors=np.where(sub["flood"], color, "none"),
                   edgecolors=color, lw=0.9, label=label)
    mx = np.array([loc[i] for i in miss["id"]])
    ax.scatter(mx[:, 0] / 1000, mx[:, 1] / 1000, marker="x", color="#e6b800", s=30, label=LABELS[3])
    ax.scatter([], [], s=46, color="#888888", label=LABELS[2])
    ax.set_aspect("equal")
    ax.set_title(LABELS[4], fontsize=11)
    ax.set_xlabel(LABELS[5] + " (EPSG:6677)")
    ax.set_ylabel(LABELS[6] + " (EPSG:6677)")
    ax.legend(fontsize=8, loc="lower right")
    fig.text(0.01, 0.005, SOURCE, fontsize=6)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "map_listing.png", dpi=150)
    (OUT / "figure_sources.txt").write_text(SOURCE + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

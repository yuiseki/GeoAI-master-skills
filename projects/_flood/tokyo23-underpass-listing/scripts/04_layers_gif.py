"""Animated map of the 23 wards: A31a (maximum scenario), OSM major roads and ward boundaries stay fixed, and the
point layers of this project are added one per frame. No elevation is drawn.

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with shapely --with rasterio --with matplotlib --with pillow python scripts/04_layers_gif.py

Writes outputs/map_listing_layers.gif (the layers added cumulatively), outputs/map_listing_layers.png (all layers)
and outputs/map_listing_layers.json (counts and sources). The A31a grid is cached under artifacts.
"""
import json
import sys
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd
import shapely
from rasterio.features import rasterize
from rasterio.transform import from_origin

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/tokyo23-underpass-listing"
RAW = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a/raw"
OUT = HERE.parent / "outputs"
A31A = "hf://datasets/yuiseki/ksj-a31a-flood-tokyo23@5b2259273128d0b79b491eb758abe0db67c4feac/parquet/flood_area.parquet"
OSM = "hf://datasets/yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664/parquet/planet_osm_line.parquet"
LIST = "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet"
KANSUI = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet"
RES = 25.0
DEPTH = {1: ("0〜0.5 m", "#deebf7"), 2: ("0.5〜3 m", "#9ecae1"), 3: ("3〜5 m", "#6baed6"),
         4: ("5〜10 m", "#4292c6"), 5: ("10〜20 m", "#2171b5"), 6: ("20 m 以上", "#084594")}
ROADS = {"motorway": (0.9, "#333333"), "trunk": (0.8, "#444444"), "primary": (0.65, "#555555"),
         "secondary": (0.45, "#777777"), "tertiary": (0.3, "#999999")}
SEQUENCE = ("listed", "unlisted", "unmatched", "kansui", "flood")
LABELS = {"listed": "OSM のアンダーパスで国の一覧に載るもの", "unlisted": "OSM のアンダーパスで一覧に載らないもの",
          "unmatched": "一覧の点で、近くに OSM のアンダーパスが無いもの", "kansui": "冠水想定箇所",
          "flood": "東京都の浸水実績の区域に入るアンダーパス (黄の輪)"}
SOURCE = ("© OpenStreetMap contributors (ODbL)。国土数値情報 洪水浸水想定区域 (A31a、想定最大規模)、「全国のアンダーパス箇所マップ」(国土交通省)、\n"
          "冠水想定箇所 (地方整備局)、東京都「浸水実績図」、国勢調査の境界 (jp-admin-2026-09) をもとに作成。A31a は河川の洪水の想定で、内水を含まない")
FRAME_MS = 1200


def visible(frame):
    """The point layers shown in a frame: all layers up to and including the frame's own."""
    if not 0 <= frame < len(SEQUENCE):
        raise IndexError(frame)
    return SEQUENCE[:frame + 1]


def burn_max(shapes_by_rank, grid):
    """Burn polygons rank by rank into grid, keeping the largest rank where polygons overlap."""
    out = grid.copy()
    for rank, mask in shapes_by_rank.items():
        out[mask] = np.maximum(out[mask], rank)
    return out


def road_class(highway):
    return highway.replace("_link", "")


def main():
    c = duckdb.connect()
    c.execute("load spatial; set threads=8")
    c.execute(f"create table wards as select name, st_transform(geometry, 'EPSG:4612', 'EPSG:6677', always_xy := true) g from '{RAW / 'wards.parquet'}'")
    c.execute("create table area as select st_union_agg(g) g from wards")
    wards = [(n, shapely.from_wkb(bytes(w))) for n, w in c.execute("select name, st_aswkb(g) from wards").fetchall()]
    x0, y0, x1, y1 = c.execute("select st_xmin(g), st_ymin(g), st_xmax(g), st_ymax(g) from area").fetchall()[0]
    pad = 600.0
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    width, height = int(np.ceil((x1 - x0) / RES)), int(np.ceil((y1 - y0) / RES))
    transform = from_origin(x0, y1, RES, RES)

    cache = ART / "a31a_max_25m.npz"
    if cache.exists():
        z = np.load(cache)
        grid, a31a_rows = z["grid"], int(z["rows"])
    else:
        q = c.execute(f"""select class_code, st_aswkb(st_transform(geometry, 'EPSG:6668', 'EPSG:6677', always_xy := true))
            from '{A31A}' where category = 'maximum'""")
        grid = np.zeros((height, width), np.uint8)
        a31a_rows = 0
        while rows := q.fetchmany(2000):
            by_rank = {}
            for code, wkb in rows:
                by_rank.setdefault(int(code), []).append(shapely.from_wkb(bytes(wkb)))
                a31a_rows += 1
            masks = {r: rasterize([(g, 1) for g in gs], out_shape=grid.shape, transform=transform, all_touched=True,
                                  dtype=np.uint8).astype(bool) for r, gs in by_rank.items()}
            grid = burn_max(masks, grid)
        inside = rasterize([(g, 1) for _, g in wards], out_shape=grid.shape, transform=transform, dtype=np.uint8).astype(bool)
        grid[~inside] = 0
        np.savez_compressed(cache, grid=grid, rows=a31a_rows)

    roads = c.execute(f"""select highway, st_aswkb(st_intersection(st_transform(way, 'EPSG:3857', 'EPSG:6677', always_xy := true), a.g))
        from '{OSM}', area a where highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link',
        'secondary','secondary_link','tertiary','tertiary_link')
        and st_intersects(st_transform(way, 'EPSG:3857', 'EPSG:6677', always_xy := true), a.g)""").fetchall()
    kansui = np.array(c.execute(f"""select st_x(p), st_y(p) from (select st_transform(st_point(k.lon, k.lat), 'OGC:CRS84', 'EPSG:6677', always_xy := true) p
        from '{KANSUI}' k where k.pref = '東京都') t, area a where st_within(t.p, a.g)""").fetchall()).reshape(-1, 2)
    loc = {i: (x, y) for i, x, y in c.execute(f"""select id, st_x(p), st_y(p) from (select id,
        st_transform(st_point(lon, lat), 'OGC:CRS84', 'EPSG:6677', always_xy := true) p from '{LIST}')""").fetchall()}
    u = pd.read_parquet(ART / "units_main.parquet")
    miss = pd.read_csv(ART / "unmatched_list_points.csv")
    listed = u["d_list"] <= 100
    unmatched = np.array([loc[i] for i in miss["id"]]).reshape(-1, 2)

    texts = "".join(LABELS.values()) + SOURCE + "".join(v[0] for v in DEPTH.values()) + \
        "東京 23 区のアンダーパスと国の一覧 A31a 想定最大の浸水深 OSM 主要道路 ここまで表示 か所 地上距離 5 km 北 表示レイヤー (+)0123456789,"
    font = use_cjk_font(texts)
    fig, ax = plt.subplots(figsize=(11, 11))
    ax.set_facecolor("white")
    cmap = ListedColormap(["#ffffff00"] + [DEPTH[k][1] for k in range(1, 7)])
    ax.imshow(np.ma.masked_where(grid == 0, grid), extent=(x0, x0 + width * RES, y1 - height * RES, y1), cmap=cmap,
              norm=BoundaryNorm(np.arange(-0.5, 7.5, 1), cmap.N), alpha=0.75, interpolation="nearest", zorder=1)
    n_road_parts = 0
    for hw, wkb in roads:
        lw, color = ROADS[road_class(hw)]
        g = shapely.from_wkb(bytes(wkb))
        for line in getattr(g, "geoms", [g]):
            if line.geom_type != "LineString" or line.is_empty:
                continue
            xs, ys = line.xy
            ax.plot(xs, ys, color=color, lw=lw * (0.7 if hw.endswith("_link") else 1), alpha=0.75, zorder=2)
            n_road_parts += 1
    for name, g in wards:
        for poly in getattr(g, "geoms", [g]):
            xs, ys = poly.exterior.xy
            ax.plot(xs, ys, color="#3d464c", lw=0.6, zorder=3)
        rp = g.representative_point()
        ax.text(rp.x, rp.y, name, fontsize=7, ha="center", va="center", color="#263238", zorder=4,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.6, "pad": 0.5})

    art = {
        "listed": ax.scatter(u.loc[listed, "x"], u.loc[listed, "y"], s=26, c="#d62728", edgecolors="white", lw=0.4, zorder=8),
        "unlisted": ax.scatter(u.loc[~listed, "x"], u.loc[~listed, "y"], s=26, c="#1f3a68", edgecolors="white", lw=0.4, zorder=7),
        "unmatched": ax.scatter(unmatched[:, 0], unmatched[:, 1], marker="x", s=40, c="#7b3294", lw=1.4, zorder=9),
        "kansui": ax.scatter(kansui[:, 0], kansui[:, 1], marker="^", s=30, facecolors="none", edgecolors="#e66101", lw=1.0, zorder=10),
        "flood": ax.scatter(u.loc[u["flood"], "x"], u.loc[u["flood"], "y"], s=120, facecolors="none", edgecolors="#f2c200", lw=1.6, zorder=6),
    }
    counts = {"listed": int(listed.sum()), "unlisted": int((~listed).sum()), "unmatched": int(len(unmatched)),
              "kansui": int(len(kansui)), "flood": int(u["flood"].sum())}
    handles = [Line2D([], [], marker="o", color="none", markerfacecolor="#d62728", markersize=7, label=f"{LABELS['listed']} ({counts['listed']})"),
               Line2D([], [], marker="o", color="none", markerfacecolor="#1f3a68", markersize=7, label=f"{LABELS['unlisted']} ({counts['unlisted']})"),
               Line2D([], [], marker="x", color="#7b3294", linestyle="none", markersize=7, label=f"{LABELS['unmatched']} ({counts['unmatched']})"),
               Line2D([], [], marker="^", color="none", markeredgecolor="#e66101", markersize=7, label=f"{LABELS['kansui']} ({counts['kansui']})"),
               Line2D([], [], marker="o", color="none", markeredgecolor="#f2c200", markeredgewidth=1.6, markersize=11, label=f"{LABELS['flood']} ({counts['flood']})"),
               Line2D([], [], color="#555555", lw=1, label="OSM 主要道路")]
    handles += [Patch(color=DEPTH[k][1], label=f"A31a 想定最大の浸水深 {DEPTH[k][0]}") for k in range(1, 7) if (grid == k).any()]
    ax.legend(handles=handles, loc="lower right", fontsize=8, title="表示レイヤー", framealpha=0.95)
    sx, sy = x0 + 0.05 * (x1 - x0), y0 + 0.06 * (y1 - y0)
    ax.plot([sx, sx + 5000], [sy, sy], color="#111111", lw=3, solid_capstyle="butt", zorder=11)
    ax.text(sx + 2500, sy + 300, "地上距離 5 km", ha="center", va="bottom", fontsize=8, zorder=11)
    ax.annotate("北", xy=(0.96, 0.92), xytext=(0.96, 0.84), xycoords="axes fraction", textcoords="axes fraction",
                arrowprops={"arrowstyle": "-|>", "color": "#222222"}, ha="center", fontsize=9)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("東京 23 区のアンダーパスと国の一覧", fontsize=14)
    fig.text(0.01, 0.01, SOURCE, fontsize=7)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "map_listing_layers.png", dpi=130)

    from matplotlib.animation import FuncAnimation, PillowWriter
    tag = ax.text(0.02, 0.975, "", transform=ax.transAxes, ha="left", va="top", fontsize=10, zorder=20,
                  bbox={"facecolor": "white", "edgecolor": "#555555", "alpha": 0.94, "boxstyle": "round,pad=0.35"})

    def update(frame):
        keys = visible(frame)
        for k, a in art.items():
            a.set_visible(k in keys)
        tag.set_text(f"ここまで表示: {LABELS[SEQUENCE[frame]]} (+{counts[SEQUENCE[frame]]:,} か所)")
        return [tag, *art.values()]

    FuncAnimation(fig, update, frames=len(SEQUENCE), interval=FRAME_MS).save(
        OUT / "map_listing_layers.gif", writer=PillowWriter(fps=1000 / FRAME_MS), dpi=90)
    plt.close(fig)
    meta = {"crs_display": "EPSG:6677", "elevation_drawn": False, "sequence": [LABELS[k] for k in SEQUENCE],
            "frame_ms": FRAME_MS, "counts": counts, "a31a_maximum_rows": a31a_rows,
            "a31a_cells_by_rank_25m": {str(k): int((grid == k).sum()) for k in range(1, 7)},
            "a31a_rule": "25 m の格子に面を塗り、川ごとの面が重なる所は大きいランクを取る (表示のため)",
            "osm_major_road_parts": n_road_parts, "font": font,
            "sources": {"A31a": "ksj-a31a-flood-tokyo23@5b22592", "OSM": "osm-tokyo23-src-2026-08@38f7a5f",
                        "list": "mlit-underpass@4d00072", "kansui": "mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f",
                        "units": "outputs of 01_build.py"}}
    (OUT / "map_listing_layers.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()

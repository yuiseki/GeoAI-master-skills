"""Draw the four figures for the 100m allocation paper.

Run from repository root:
  /tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/make_figures.py
"""

import json
import sys
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd
import shapely
from matplotlib.colors import LogNorm
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as MPath
from pyproj import Transformer
from shapely.geometry import box

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.parent.name / PROJECT.name
OUTPUT = PROJECT / "outputs"
FIGURES = OUTPUT / "figures"
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

TEXT = (
    "東京都本土 高齢者 交通空白 優先順位 人口配分 中心点 5点 100m 一様 上位10 "
    "メッシュ 市区町村 人 対象 65歳以上 75歳以上 空白割合 順位 両方 のみ その他 "
    "八王子市 品川区 江戸川区 大田区 羽村市 町田市 瑞穂町 青梅市 あきる野市 葛飾区 "
    "荒川区 台東区 江東区 板橋区 北区 港区 多摩市 武蔵村山市 福生市 世田谷区 杉並区 "
    "練馬区 足立区 墨田区 中央区 千代田区 新宿区 文京区 目黒区 渋谷区 中野区 豊島区 "
    "三鷹市 立川市 府中市 調布市 小金井市 国分寺市 国立市 西東京市 東村山市 東久留米市 "
    "清瀬市 小平市 日野市 狛江市 東大和市 武蔵野市 昭島市 稲城市 日の出町 奥多摩町 檜原村 "
    "バス停 駅 徒歩 距離 中心 画素 推計 国勢調査 条件 回 以上 表示 注 出典 データ 版 "
    "NoData 不明 欠測 判定不能 保守的 都県境 水面 除外 比 再正規化 厳格 一様扱い "
    "図 凡例 数字 黒点 星 円 四角 色 対数 人/画素 メッシュ中心 交通空白画素 "
    "バス800m超 駅1,500m超 2019 2020 2022 2026 2026-10-26 "
    "0 1 2 3 4 5 6 7 8 9 10 20 30 40 50 100 200 500 800 1000 1500 2000 3000 "
)

COLORS = {"both": "#6a3d9a", "center": "#e66101", "wpop": "#2c7bb6", "base": "#f2f2f2"}


def mesh_bounds(code):
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def polygons(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
    return []


def polygon_path(poly):
    rings = [np.asarray(poly.exterior.coords)]
    for interior in poly.interiors:
        ring = np.asarray(interior.coords)
        if len(ring) >= 4 and abs(shapely.Polygon(ring).area) > 1e-12:
            rings.append(ring)
    codes = []
    for ring in rings:
        codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(ring) - 2) + [MPath.CLOSEPOLY])
    return MPath(np.concatenate(rings), codes)


def add_polygon(ax, geom, **kwargs):
    for poly in polygons(geom):
        ax.add_patch(PathPatch(polygon_path(poly), **kwargs))


def load_geometry():
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial;")
    rows = con.execute(
        f"SELECT code5, name, ST_AsWKB(geometry) "
        f"FROM '{ARTIFACTS / 'mainland-municipalities.parquet'}' ORDER BY code5"
    ).fetchall()
    transformer = Transformer.from_crs(4612, 6677, always_xy=True)

    def project(geom):
        return shapely.transform(
            geom,
            lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1])),
        )

    municipalities = []
    for code5, name, wkb in rows:
        geom = project(shapely.from_wkb(bytes(wkb)))
        municipalities.append((code5, name, geom))
    union = shapely.union_all([geom for _, _, geom in municipalities]).buffer(0)
    return municipalities, union, transformer


def mesh_cells(meshes, union, transformer):
    def project(geom):
        return shapely.transform(
            geom,
            lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1])),
        )

    cells = {}
    for code in meshes["mesh"]:
        geom = project(box(*mesh_bounds(code)))
        clipped = shapely.intersection(geom, union)
        if not clipped.is_empty:
            cells[code] = clipped
    return cells


def draw_base(ax, cells, municipalities, union):
    for geom in cells.values():
        add_polygon(ax, geom, facecolor=COLORS["base"], edgecolor="#d8d8d8",
                    linewidth=0.16, zorder=1)
    for _, _, geom in municipalities:
        add_polygon(ax, geom, facecolor="none", edgecolor="#9b9b9b",
                    linewidth=0.32, zorder=2)
    add_polygon(ax, union, facecolor="none", edgecolor="#333333", linewidth=0.75, zorder=3)


def figure_top10_map():
    summary = json.loads((OUTPUT / "allocations-summary.json").read_text())
    main = summary["summaries"]["main"]
    center_top = main["top10"]["center"]
    wpop_top = main["top10"]["wpop"]
    meshes = pd.read_parquet(ARTIFACTS / "mesh-allocations.parquet")
    municipalities, union, transformer = load_geometry()
    cells = mesh_cells(meshes, union, transformer)

    fig = plt.figure(figsize=(16, 6.8), facecolor="white")
    axes = [
        fig.add_axes([0.012, 0.140, 0.475, 0.650]),
        fig.add_axes([0.512, 0.140, 0.475, 0.650]),
    ]
    titles = ["中心点の上位10", "100m人口重みの上位10"]
    for ax, top, panel in zip(axes, (center_top, wpop_top), ("center", "wpop")):
        draw_base(ax, cells, municipalities, union)
        for rank, code in enumerate(top, start=1):
            overlap = code in center_top and code in wpop_top
            color = COLORS["both"] if overlap else COLORS[panel]
            geom = cells.get(code)
            if geom is None:
                continue
            add_polygon(ax, geom, facecolor=color, edgecolor="#1a1a1a",
                        linewidth=0.7, alpha=0.96, zorder=4)
            point = geom.representative_point()
            ax.text(point.x, point.y, str(rank), ha="center", va="center", fontsize=8.5,
                    color="white", weight="bold", zorder=6,
                    bbox=dict(boxstyle="circle,pad=0.20", facecolor="#1a1a1a",
                              edgecolor="white", linewidth=0.45, alpha=0.88))
        ax.set_aspect("equal")
        ax.set_anchor("N")
        ax.axis("off")
        ax.set_title(titles[0 if panel == "center" else 1], fontsize=14, weight="bold",
                     color="#20252a", pad=5)
    xmin, ymin, xmax, ymax = union.bounds
    for ax in axes:
        ax.set_xlim(xmin - 1500, xmax + 1500)
        ax.set_ylim(ymin - 1500, ymax + 1500)

    handles = [
        Patch(facecolor=COLORS["both"], edgecolor="#1a1a1a", label="両方の上位10（2メッシュ）"),
        Patch(facecolor=COLORS["center"], edgecolor="#1a1a1a", label="中心点だけの上位10"),
        Patch(facecolor=COLORS["wpop"], edgecolor="#1a1a1a", label="100m人口重みだけの上位10"),
        Patch(facecolor=COLORS["base"], edgecolor="#d8d8d8", label="その他のメッシュ（1,380）"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 0.058), handlelength=1.5, columnspacing=1.8)
    axes[0].text(0.01, 0.01,
                 "両方の上位10：八王子市 53394207、品川区 53393610\n"
                 "数字は各配分の順位。色は各パネルの上位10。",
                 transform=axes[0].transAxes, fontsize=7.8, va="bottom", ha="left",
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.9,
                           edgecolor="#cccccc"))
    # 10 km scale bar
    x0, y0 = xmin + 2500, ymin + 2500
    axes[0].plot([x0, x0 + 10000], [y0, y0], color="#222222", linewidth=3, solid_capstyle="butt")
    axes[0].text(x0 + 5000, y0 + 350, "10 km", ha="center", va="bottom", fontsize=8,
                 bbox=dict(facecolor="white", edgecolor="none", pad=1.5, alpha=0.8))

    fig.text(0.012, 0.965, "1kmメッシュの高齢者交通空白優先順位は、メッシュ内の人口配分でどう変わるか",
             fontsize=19, weight="bold", color="#20252a", ha="left", va="top")
    fig.text(0.012, 0.915,
             "東京都本土53市区町村｜2020年国勢調査3次メッシュ（1km）｜バス停800m超かつ運行中駅1,500m超",
             fontsize=10, color="#414b53", ha="left", va="top")
    fig.text(0.012, 0.012,
             "出典：国勢調査2020（e-Stat）／WorldPop R2025A 100m 2020／KSJ P11バス停2022年度／駅データ2026-07-31／OSM道路2026-08-31／行政界2026-09\n"
             "投影：EPSG:6677（m）。メッシュは行政界の陸域で切った。白い部分は水域と、中心が対象市区町村の外にある1kmメッシュ。中心点が判定不能の40メッシュは順位から除外。",
             fontsize=8, color="#5c6469", ha="left", va="bottom", linespacing=1.45)

    metadata = {
        "question": "中心点と100m人口重みで、上位10のメッシュはどこで重なるか",
        "source": "outputs/allocations-summary.json; artifacts/_transit/elderly-transit-100m-allocation/mesh-allocations.parquet",
        "n_meshes": int(len(meshes)), "n_center_top10": len(center_top),
        "n_wpop_top10": len(wpop_top), "overlap": sorted(set(center_top) & set(wpop_top)),
        "crs": "EPSG:6677", "unit": "1km mesh", "value": "target age65 by allocation",
        "font": use_cjk_font(TEXT), "renderer": "project make_figures.py",
    }
    path = FIGURES / "fig1-top10-map.png"
    fig.savefig(path, dpi=180, metadata={"Description": json.dumps(metadata, ensure_ascii=False)})
    path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    plt.close(fig)
    return metadata


def figure_dumbbell_scatter():
    meshes = pd.read_parquet(ARTIFACTS / "mesh-allocations.parquet")
    summary = json.loads((OUTPUT / "allocations-summary.json").read_text())
    main = summary["summaries"]["main"]
    center_top = main["top10"]["center"]
    wpop_top = main["top10"]["wpop"]
    union = sorted(set(center_top) | set(wpop_top), key=lambda c: (
        -meshes.loc[meshes["mesh"] == c, "wpop_age65_main_500"].fillna(-1).iloc[0], c))
    rows = meshes[meshes["mesh"].isin(union)].copy()
    rows = rows.sort_values("wpop_age65_main_500", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8.6), facecolor="white",
                             gridspec_kw={"width_ratios": [1, 1.12]})
    fig.subplots_adjust(left=0.055, right=0.985, top=0.82, bottom=0.12, wspace=0.42)

    ax = axes[0]
    center_gap = meshes[(meshes["age65"].notna()) & (meshes["center_gap_main_500"] == 1)]
    scatter = ax.scatter(center_gap["age65"], center_gap["wpop_age65_main_500"],
                         c=center_gap["wpop_fraction_main_500"], cmap="viridis",
                         s=22, edgecolor="white", linewidth=0.35, vmin=0, vmax=1, zorder=3)
    limit = max(center_gap["age65"].max(), 100) * 1.04
    ax.plot([0, limit], [0, limit], color="#777777", linestyle="--", linewidth=1,
            label="中心点＝全員（1:1）", zorder=2)
    ax.set_xlim(0, limit)
    ax.set_ylim(0, max(center_gap["wpop_age65_main_500"].max(), 100) * 1.18)
    ax.set_xlabel("メッシュの65歳以上人数（人）", fontsize=10)
    ax.set_ylabel("100m人口重みで空白に住む65歳以上人数（人）", fontsize=10)
    ax.set_title("中心点が空白の116メッシュ", fontsize=13, weight="bold", pad=8)
    ax.grid(color="#e6e6e6", linewidth=0.6)
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    ax.text(0.98, 0.04,
            f"n = {len(center_gap)}\n中央値 {center_gap['wpop_fraction_main_500'].median():.1%}\n"
            f"0人は {(center_gap['wpop_age65_main_500'].fillna(0) == 0).sum()}メッシュ",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.9, edgecolor="#cccccc"))
    for code, dx, dy, ha in [("53393610", -14, 18, "right"), ("53394256", -14, 14, "right"),
                             ("53394648", 12, 18, "left"), ("53394207", 14, -12, "left"),
                             ("53393253", -12, -18, "right")]:
        row = center_gap[center_gap["mesh"] == code]
        if row.empty:
            continue
        ax.annotate(f"{code}\n{row.iloc[0]['municipality']}",
                    (row.iloc[0]["age65"], row.iloc[0]["wpop_age65_main_500"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=7, color="#222222",
                    ha=ha, arrowprops=dict(arrowstyle="-", color="#888888", linewidth=0.6))
    cbar = fig.colorbar(scatter, ax=ax, fraction=0.05, pad=0.035)
    cbar.set_label("100m人口重みの空白割合", fontsize=8.5, labelpad=2)

    ax = axes[1]
    plot_rows = rows[rows["center_age65_main_500"].notna()].copy()
    plot_rows = plot_rows.sort_values("wpop_age65_main_500", ascending=False)
    y = np.arange(len(plot_rows))
    for yi, (_, row) in zip(y, plot_rows.iterrows()):
        ax.plot([row["center_age65_main_500"], row["wpop_age65_main_500"]], [yi, yi],
                color="#bdbdbd", linewidth=1.4, zorder=1)
    ax.scatter(plot_rows["center_age65_main_500"], y, s=52, color=COLORS["center"],
               edgecolor="white", linewidth=0.6, zorder=3, label="中心点")
    ax.scatter(plot_rows["wpop_age65_main_500"], y, s=52, color=COLORS["wpop"],
               edgecolor="white", linewidth=0.6, zorder=4, label="100m人口重み")
    labels = [f"{row['mesh']}  {row['municipality']}" for _, row in plot_rows.iterrows()]
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7.6)
    ax.invert_yaxis()
    ax.set_xlabel("対象65歳以上人数（人）", fontsize=10)
    ax.set_title("上位10の入れ替わり（中心点 vs 100m人口重み）", fontsize=13, weight="bold", pad=26)
    ax.grid(axis="x", color="#e6e6e6", linewidth=0.6)
    ax.axvline(0, color="#777777", linewidth=0.8)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, fontsize=8.5,
              frameon=False)
    fig.text(0.545, 0.032, "中心点が判定不能の53393326は除く。中心点0は、中心が空白でないメッシュ。",
             fontsize=7.5, color="#5c6469", ha="left", va="bottom")

    fig.text(0.055, 0.965, "中心点が空白でも、住んでいる場所は空白とは限らない",
             fontsize=19, weight="bold", color="#20252a", ha="left", va="top")
    fig.text(0.055, 0.920,
             "中心点の2値判定と、100m WorldPopで配分した対象人数。点が1:1線より下にあるほど、中心点方式が対象人数を大きく見積もる。",
             fontsize=10, color="#414b53", ha="left", va="top")
    fig.text(0.055, 0.010,
             "出典：国勢調査2020／WorldPop R2025A 100m 2020／徒歩ネットワークはOSM 2026-08-31、EPSG:6677。",
             fontsize=8.5, color="#4c5459", ha="left", va="bottom")
    metadata = {
        "question": "中心点が空白のメッシュで、100m人口重みの対象人数はどれだけ小さいか；上位10はどう入れ替わるか",
        "source": "outputs/mesh-allocations.parquet; outputs/allocations-summary.json",
        "n_center_gap": int(len(center_gap)), "n_dumbbell": int(len(plot_rows)),
        "font": use_cjk_font(TEXT), "renderer": "project make_figures.py",
    }
    path = FIGURES / "fig2-dumbbell-scatter.png"
    fig.savefig(path, dpi=180, metadata={"Description": json.dumps(metadata, ensure_ascii=False)})
    path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    plt.close(fig)
    return metadata


def figure_pixel_examples():
    pixels = pd.read_parquet(ARTIFACTS / "pixel-access.parquet")
    buses = pd.read_parquet(ARTIFACTS / "bus-buffer.parquet")
    stations = pd.read_parquet(ARTIFACTS / "stations-buffer.parquet")
    stations = stations[stations["e_status"] == 0]
    examples = ["53393610", "53394648", "53393252", "53394207"]
    meshes = pd.read_parquet(ARTIFACTS / "mesh-allocations.parquet").set_index("mesh")
    vmax = float(pixels.loc[pixels["mesh"].isin(examples), "value"].max())

    fig, axes = plt.subplots(2, 2, figsize=(14.5, 12.0), facecolor="white")
    fig.subplots_adjust(left=0.04, right=0.97, top=0.82, bottom=0.13, wspace=0.08, hspace=0.25)
    sm = plt.cm.ScalarMappable(norm=LogNorm(vmin=0.05, vmax=vmax), cmap="YlGnBu")
    for ax, code in zip(axes.ravel(), examples):
        west, south, east, north = mesh_bounds(code)
        sub = pixels[pixels["mesh"] == code].copy()
        values = np.full((10, 15), np.nan)
        status = np.full((10, 15), "", dtype=object)
        gap = np.zeros((10, 15), dtype=bool)
        for _, row in sub.iterrows():
            col = int(np.floor((row["lon"] - west) * 1200))
            rowi = int(np.floor((row["lat"] - south) * 1200))
            if not (0 <= col < 15 and 0 <= rowi < 10):
                continue
            status[rowi, col] = row["status"]
            gap[rowi, col] = bool(row["gap_main_500"] == 1)
            if row["status"] == "positive":
                values[rowi, col] = row["value"]
        xedges = west + np.arange(16) / 1200
        yedges = south + np.arange(11) / 1200
        masked = np.ma.masked_where(np.isnan(values), values)
        ax.pcolormesh(xedges, yedges, masked, cmap="YlGnBu",
                      norm=LogNorm(vmin=0.05, vmax=vmax), shading="flat", zorder=2)
        for rowi in range(10):
            for col in range(15):
                if status[rowi, col] == "nodata" or status[rowi, col] == "":
                    ax.add_patch(plt.Rectangle((xedges[col], yedges[rowi]),
                                               1 / 1200, 1 / 1200,
                                               facecolor="#cfcfcf", edgecolor="white",
                                               linewidth=0.25, zorder=2))
                elif status[rowi, col] == "zero":
                    ax.add_patch(plt.Rectangle((xedges[col], yedges[rowi]),
                                               1 / 1200, 1 / 1200,
                                               facecolor="white", edgecolor="white",
                                               linewidth=0.25, zorder=2))
        gy, gx = np.where(gap)
        ax.scatter(xedges[gx] + 0.5 / 1200, yedges[gy] + 0.5 / 1200,
                   s=5, color="black", zorder=4, label="交通空白画素")
        # bus stops and stations near the mesh
        pad = 0.0016
        bb = buses[(buses["lon"].between(west - pad, east + pad))
                   & (buses["lat"].between(south - pad, north + pad))]
        st = stations[(stations["lon"].between(west - pad, east + pad))
                      & (stations["lat"].between(south - pad, north + pad))]
        ax.scatter(bb["lon"], bb["lat"], s=17, facecolor="white", edgecolor="#0072B2",
                   linewidth=0.9, zorder=6, label="バス停")
        ax.scatter(st["lon"], st["lat"], s=24, marker="s", facecolor="white",
                   edgecolor="#D55E00", linewidth=1.0, zorder=7, label="駅")
        ax.scatter([(west + east) / 2], [(south + north) / 2], marker="*", s=180,
                   facecolor="white", edgecolor="black", linewidth=1.0, zorder=8,
                   label="メッシュ中心")
        record = meshes.loc[code]
        center_target = record["center_age65_main_500"]
        center_text = "判定不能" if pd.isna(center_target) else f"{center_target:.0f}"
        ax.set_title(
            f"{code}  {record['municipality']}  ｜  65歳以上 {record['age65']:.0f}人\n"
            f"中心点 {center_text}人 → 100m人口重み {record['wpop_age65_main_500']:.0f}人"
            f"（空白割合 {record['wpop_fraction_main_500']:.1%}）",
            fontsize=10.5, weight="bold", pad=6)
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_aspect(1 / np.cos(np.deg2rad((south + north) / 2)))
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#777777")
            spine.set_linewidth(0.5)
        # 200 m scale bar
        x0 = west + 0.0007
        y0 = south + 0.0007
        ax.plot([x0, x0 + 200 / (111320 * np.cos(np.deg2rad((south + north) / 2)))], [y0, y0],
                color="black", linewidth=2.5, solid_capstyle="butt", zorder=9)
        ax.text(x0 + 100 / (111320 * np.cos(np.deg2rad((south + north) / 2))), y0 + 0.00035,
                "200 m", ha="center", va="bottom", fontsize=7,
                bbox=dict(facecolor="white", edgecolor="none", pad=1.0, alpha=0.8), zorder=9)

    handles = [
        Patch(facecolor="#cfcfcf", edgecolor="white", label="NoData"),
        Patch(facecolor="white", edgecolor="#bbbbbb", label="0人"),
        plt.Line2D([], [], marker="o", color="black", linestyle="none", markersize=3,
                   label="交通空白画素"),
        plt.Line2D([], [], marker="o", markerfacecolor="white", markeredgecolor="#0072B2",
                   linestyle="none", markersize=6, label="バス停"),
        plt.Line2D([], [], marker="s", markerfacecolor="white", markeredgecolor="#D55E00",
                   linestyle="none", markersize=6, label="駅"),
        plt.Line2D([], [], marker="*", markerfacecolor="white", markeredgecolor="black",
                   linestyle="none", markersize=10, label="メッシュ中心"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=6, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 0.055))
    cbar = fig.colorbar(sm, ax=axes, orientation="horizontal", fraction=0.027, pad=0.075,
                        aspect=38)
    cbar.set_label("WorldPop 2020 の推計人口（人/画素、対数）", fontsize=9)
    fig.text(0.04, 0.965, "メッシュ内の100m画素：だれが空白に住んでいるか",
             fontsize=19, weight="bold", color="#20252a", ha="left", va="top")
    fig.text(0.04, 0.923,
             "色はWorldPop 2020の推計人口、黒点はバス停800m超かつ駅1,500m超の画素。中心の星が空白でも、人口の多くは空白の外にいることがある。",
             fontsize=10, color="#414b53", ha="left", va="top")
    fig.text(0.04, 0.012,
             "出典：WorldPop R2025A 100m 2020／KSJ P11バス停2022年度／駅データ2026-07-31／OSM道路2026-08-31。画素の距離は徒歩ネットワーク（EPSG:6677）。",
             fontsize=8, color="#5c6469", ha="left", va="bottom")
    metadata = {
        "question": "中心点が空白のメッシュで、100m画素の人口と空白画素はどう配置されているか",
        "source": "outputs/pixel-access.parquet; artifacts/.../bus-buffer.parquet; stations-buffer.parquet",
        "examples": examples, "vmax": vmax, "font": use_cjk_font(TEXT),
        "renderer": "project make_figures.py",
    }
    path = FIGURES / "fig3-pixel-examples.png"
    fig.savefig(path, dpi=180, metadata={"Description": json.dumps(metadata, ensure_ascii=False)})
    path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    plt.close(fig)
    return metadata


def figure_robustness_matrix():
    summary = json.loads((OUTPUT / "allocations-summary.json").read_text())
    diagnostics = json.loads((OUTPUT / "diagnostics.json").read_text())
    columns = {}
    for section in ("main", "tight", "loose", "age75", "snap200"):
        for allocation, codes in summary["summaries"][section]["top10"].items():
            columns[f"{section}_{allocation}"] = set(codes)
    for variant, data in summary["summaries"]["nodata_variants"].items():
        columns[f"quality_{variant}"] = set(data["top10"]["wpop"])
    for allocation, codes in summary["summaries"]["ratio_restricted"]["top10"].items():
        columns[f"ratio_{allocation}"] = set(codes)
    columns["five_conservative"] = set(summary["summaries"]["five_conservative"]["top10"]["five"])
    for allocation, codes in diagnostics["border_sensitivity"]["top10"].items():
        columns[f"border_{allocation}"] = set(codes)

    counts = {code: sum(code in values for values in columns.values()) for code in set().union(*columns.values())}
    selected = sorted([code for code, count in counts.items() if count >= 6],
                      key=lambda code: (-counts[code], code))
    meshes = pd.read_parquet(ARTIFACTS / "mesh-allocations.parquet").set_index("mesh")
    matrix = np.array([[1 if code in columns[name] else 0 for name in columns] for code in selected])

    fig, ax = plt.subplots(figsize=(16, 9.2), facecolor="white")
    fig.subplots_adjust(left=0.24, right=0.9, top=0.8, bottom=0.18)
    cmap = matplotlib.colors.ListedColormap(["#f7f7f7", COLORS["wpop"]])
    ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
    for x in range(len(columns) + 1):
        ax.axvline(x - 0.5, color="white", linewidth=1.1)
    for y in range(len(selected) + 1):
        ax.axhline(y - 0.5, color="white", linewidth=1.1)
    ax.set_yticks(np.arange(len(selected)))
    ax.set_yticklabels([f"{code}  {meshes.loc[code, 'municipality']}" for code in selected],
                       fontsize=8)
    short = {
        "main_center": "中心点", "main_five": "5点", "main_wpop": "100m", "main_uniform": "一様",
        "tight_center": "中心点", "tight_five": "5点", "tight_wpop": "100m", "tight_uniform": "一様",
        "loose_center": "中心点", "loose_five": "5点", "loose_wpop": "100m", "loose_uniform": "一様",
        "age75_center": "中心点", "age75_five": "5点", "age75_wpop": "100m", "age75_uniform": "一様",
        "snap200_center": "中心点", "snap200_five": "5点", "snap200_wpop": "100m", "snap200_uniform": "一様",
        "quality_main": "再正規化", "quality_strict": "厳格除外",
        "quality_nodata_uniform": "一様扱い", "quality_exclude_nodata": "NoData除外",
        "ratio_center": "中心点", "ratio_wpop": "100m",
        "five_conservative": "5点", "border_center": "中心点", "border_five": "5点",
        "border_wpop": "100m", "border_uniform": "一様",
    }
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels([short.get(name, name) for name in columns], rotation=90, fontsize=7)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for yi, code in enumerate(selected):
        ax.text(len(columns) + 0.3, yi, f"{counts[code]}/{len(columns)}", va="center",
                ha="left", fontsize=8, color="#333333")
    groups = [("main_", "主", 4), ("tight_", "バス500/駅1,000", 4),
              ("loose_", "バス1,000/駅2,000", 4), ("age75_", "75歳以上", 4),
              ("snap200_", "スナップ200m", 4), ("quality_", "NoData処理", 4),
              ("ratio_", "比0.5–2.0", 2), ("five_conservative", "5点保守", 1),
              ("border_", "都県境", 4)]
    position = 0
    for prefix, label, width in groups:
        ax.text(position + width / 2 - 0.5, -0.85, label, ha="center", va="bottom",
                fontsize=7.5, color="#333333", rotation=0)
        position += width
        if position < len(columns):
            ax.axvline(position - 0.5, color="#333333", linewidth=0.8)
    fig.text(0.03, 0.955, "top10に入るメッシュは、条件を変えるとどれだけ残るか",
             fontsize=19, weight="bold", color="#20252a", ha="left", va="top")
    fig.text(0.03, 0.915,
             f"31の条件（配分・閾値・年齢・スナップ・NoData・比・都県境）のうち、top10に入った回数。6回以上の{len(selected)}メッシュを表示。",
             fontsize=10, color="#414b53", ha="left", va="top")
    fig.text(0.03, 0.035,
             "条件は独立ではない。回数は頑健性の点数ではなく、どの条件でも残るメッシュがほとんどないことを示す要約。右端の数字は31条件中の回数。",
             fontsize=8.5, color="#4c5459", ha="left", va="top")
    metadata = {
        "question": "配分・閾値・年齢・NoData・比・都県境を変えたとき、top10に入るメッシュはどれだけ残るか",
        "source": "outputs/allocations-summary.json; outputs/diagnostics.json",
        "n_conditions": len(columns), "n_meshes_shown": len(selected),
        "counts": {code: counts[code] for code in selected},
        "font": use_cjk_font(TEXT), "renderer": "project make_figures.py",
    }
    path = FIGURES / "fig4-robustness-matrix.png"
    fig.savefig(path, dpi=180, metadata={"Description": json.dumps(metadata, ensure_ascii=False)})
    path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    plt.close(fig)
    return metadata


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    font = use_cjk_font(TEXT)
    print(f"font: {font}")
    for name, function in (
        ("fig1", figure_top10_map),
        ("fig2", figure_dumbbell_scatter),
        ("fig3", figure_pixel_examples),
        ("fig4", figure_robustness_matrix),
    ):
        print(f"{name}: {function()}")


if __name__ == "__main__":
    main()

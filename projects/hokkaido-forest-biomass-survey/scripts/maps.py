"""Draw the analysed cells as squares on municipal boundaries; do not recompute the analysis.

Run: uvx --with duckdb --with shapely --with numpy --with matplotlib python projects/hokkaido-forest-biomass-survey/scripts/maps.py

Values come from outputs/cell_metrics.csv and outputs/summary.json. Only the
municipal boundaries are read here, from a pinned jp-admin revision.
"""

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
OUTPUT = PROJECT / "outputs"
ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
ADMIN_URL = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
DROP_BREAKS = [-20, -10, -5, -2, 2, 5, 10, 20]
FOREST_BREAKS = [0.5, 0.8, 0.9]


def fit_grid(records):
    """Cell edges from the centres; stop if a centre is off the regular grid."""
    rows = np.array([r["cell_row"] for r in records], dtype=float)
    cols = np.array([r["cell_col"] for r in records], dtype=float)
    lon = np.array([float(r["lon"]) for r in records])
    lat = np.array([float(r["lat"]) for r in records])
    lon_step, lon0 = np.polyfit(cols, lon, 1)
    lat_step, lat0 = np.polyfit(rows, lat, 1)
    step = lon_step
    if abs(lat_step + step) > 1e-9 * max(1.0, abs(step)):
        raise ValueError("cells are not square in degrees")
    residual = max(np.abs(lon - (lon0 + cols * lon_step)).max(), np.abs(lat - (lat0 + rows * lat_step)).max())
    if residual > step * 1e-3:
        raise ValueError(f"cell centre off grid by {residual} degrees")
    r0, r1, c0, c1 = int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())
    west = lon0 + (c0 - 0.5) * step
    east = lon0 + (c1 + 0.5) * step
    north = lat0 - (r0 - 0.5) * step
    south = lat0 - (r1 + 0.5) * step
    return {"step": step, "row0": r0, "col0": c0, "shape": (r1 - r0 + 1, c1 - c0 + 1),
            "extent": [west, east, south, north], "lon0": lon0, "lat0": lat0}


def grid_array(records, grid, value):
    """Rows north to south, columns west to east; cells without a record stay NaN."""
    arr = np.full(grid["shape"], np.nan)
    for r in records:
        v = value(r)
        if v is not None:
            arr[r["cell_row"] - grid["row0"], r["cell_col"] - grid["col0"]] = v
    return arr


def classify(values, breaks):
    """Class i holds breaks[i-1] <= v < breaks[i]; NaN stays NaN."""
    out = np.digitize(values, breaks, right=False).astype(float)
    out[np.isnan(values)] = np.nan
    return out


def municipality_of(lon, lat, munis):
    """Names of every polygon holding the point; jp-admin polygons overlap at shared borders."""
    from shapely.geometry import Point

    pt = Point(lon, lat)
    return "/".join(name for name, geom in munis if geom.covers(pt))


def cell_box(grid, row, col):
    step = grid["step"]
    lon = grid["lon0"] + col * step
    lat = grid["lat0"] - row * step
    return lon - step / 2, lat - step / 2, step


def read_records():
    with (OUTPUT / "cell_metrics.csv").open(newline="") as fh:
        records = list(csv.DictReader(fh))
    for r in records:
        r["cell_row"], r["cell_col"] = int(r["cell_row"]), int(r["cell_col"])
    return records


def eligible(r):
    return (float(r["cover_frac"]) >= 0.95 and float(r["forest_frac"]) >= 0.8 and float(r["drop"]) > 0
            and int(r["valid_pixels_2010"]) >= 80 and int(r["valid_pixels_2025"]) >= 80)


def read_municipalities(extent):
    import duckdb
    from shapely import from_wkb
    from shapely.geometry import box

    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs")
    rows = con.sql(f"select name, ST_AsWKB(geometry) from '{ADMIN_URL}' "
                   "where pref_code = '01' and geometry is not null").fetchall()
    west, east, south, north = extent
    view = box(west - 0.05, south - 0.05, east + 0.05, north + 0.05)
    out = []
    for name, wkb in rows:
        geom = from_wkb(bytes(wkb))
        if geom.intersects(view):
            out.append((name, geom.intersection(view)))
    return out, duckdb.__version__


def draw_base(ax, munis, extent, mid_lat, land=True):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath

    def patch(geom, **kw):
        polys = getattr(geom, "geoms", [geom])
        for poly in polys:
            if poly.geom_type != "Polygon" or poly.is_empty:
                continue
            verts, codes = [], []
            for ring in [poly.exterior, *poly.interiors]:
                xy = list(ring.coords)
                verts += xy
                codes += [MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), **kw))

    for _, geom in munis:
        if land:
            patch(geom, facecolor="#efece6", edgecolor="none", zorder=0)
    ax.set_facecolor("#dbe9f2")
    west, east, south, north = extent
    ax.set_xlim(west - 0.02, east + 0.02)
    ax.set_ylim(south - 0.02, north + 0.02)
    ax.set_aspect(1 / math.cos(math.radians(mid_lat)))
    return patch


def draw_boundaries(ax, munis, patch):
    for _, geom in munis:
        patch(geom, facecolor="none", edgecolor="#4d4d4d", linewidth=0.6, zorder=4)


def label_municipalities(ax, munis, extent, min_area=0.01):
    west, east, south, north = extent
    labels = []
    for name, geom in munis:
        if geom.area < min_area:
            continue
        p = geom.representative_point()
        if west <= p.x <= east and south <= p.y <= north:
            ax.text(p.x, p.y, name, fontsize=8, ha="center", va="center", color="#222222", zorder=6,
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.7})
            labels.append(name)
    return labels


def main():
    sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch, Rectangle
    from cjk_font import use_cjk_font

    summary = json.loads((OUTPUT / "summary.json").read_text())
    records = read_records()
    grid = fit_grid(records)
    extent = grid["extent"]
    mid_lat = (extent[2] + extent[3]) / 2
    munis, duckdb_version = read_municipalities(extent)
    names = "".join(sorted({n for n, _ in munis}))
    font = use_cjk_font(
        names + "北海道東部 推定AGB密度の差 2010年から2025年 低下 増加 ほぼ変化なし Mg/ha 森林率 ForTy 2020年 "
        "クラス1〜3 分類図の覆い95%未満 交差なし 集計面 現地照合候補 主条件 生の上位のみ 設定を変えても残る "
        "主条件のみ 主母集団 経度 緯度 度 以上 未満 市町村境界 jp-admin 版 面 順位 0123456789.,()≥<−-:/%")
    sources = {
        "ctrees_revision": summary["inputs"]["ctrees"]["revision"],
        "forty_revision": summary["inputs"]["forty"]["revision"],
        "jp_admin_revision": ADMIN_REV,
    }
    common = {
        "sources": ["outputs/cell_metrics.csv", "outputs/summary.json", ADMIN_URL],
        **sources,
        "crs": "EPSG:4326 degrees for cells; jp-admin boundaries are EPSG:4612 drawn without transformation "
               "(difference about 1 m, below the drawn line width)",
        "aspect": f"1/cos({mid_lat:.3f} deg)",
        "cells_drawn": len(records),
        "cell_size_deg": grid["step"],
        "duckdb_version": duckdb_version,
        "font": font,
        "warning": "model-estimate screening; not observed forest loss",
    }
    footer = (f"集計面 {len(records):,} (EPSG:4326、1 面 {grid['step']:.5f} 度角)。CTrees {sources['ctrees_revision'][:7]}、"
              f"ForTy {sources['forty_revision'][:7]}、市町村境界 jp-admin {ADMIN_REV[:7]}。")

    # 1. drop map
    drop = grid_array(records, grid, lambda r: float(r["drop"]))
    cls = classify(drop, DROP_BREAKS)
    colours = list(reversed(plt.get_cmap("BrBG")(np.linspace(0.05, 0.95, len(DROP_BREAKS) + 1))))
    counts = [int(np.sum(cls == i)) for i in range(len(DROP_BREAKS) + 1)]
    fig, ax = plt.subplots(figsize=(11, 8.6), constrained_layout=True)
    patch = draw_base(ax, munis, extent, mid_lat)
    ax.imshow(cls, extent=extent, origin="upper", interpolation="nearest", zorder=2,
              cmap=ListedColormap(colours), norm=BoundaryNorm(np.arange(-0.5, len(colours)), len(colours)))
    draw_boundaries(ax, munis, patch)
    labels = label_municipalities(ax, munis, extent)
    edges = ["", *[f"{b:g}" for b in DROP_BREAKS], ""]
    handles = []
    for i, c in enumerate(colours):
        lo, hi = edges[i], edges[i + 1]
        text = f"{hi} 未満" if not lo else (f"{lo} 以上" if not hi else f"{lo} 〜 {hi}")
        handles.append(Patch(facecolor=c, edgecolor="#888888", label=f"{text} ({counts[i]:,})"))
    handles.reverse()
    ax.legend(handles=handles, title="推定AGB密度の差 2010年−2025年 (Mg/ha)\n正 = 低下", loc="upper left",
              bbox_to_anchor=(1.01, 1), fontsize=8, title_fontsize=8.5, framealpha=0.95)
    ax.set(xlabel="経度 (度)", ylabel="緯度 (度)", title="北海道東部 推定AGB密度の差 (2010年から2025年)")
    fig.text(0.5, -0.01, footer, ha="center", fontsize=8)
    fig.savefig(OUTPUT / "drop-map.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    (OUTPUT / "drop-map.json").write_text(json.dumps({
        "question": "CTreesの推定AGB密度の差は、解析範囲のどこで正 (低下) で、どこで負か",
        **common, "value": "drop = agb_2010 - agb_2025 (Mg/ha, model means)", "kind": "change",
        "breaks_mg_ha": DROP_BREAKS, "breaks_reason": "fixed, symmetric around 0; ±2 Mg/ha shown as near zero",
        "class_counts": counts, "nodata": int(np.isnan(drop).sum() - (np.prod(grid["shape"]) - len(records))),
        "palette": "BrBG reversed (brown = drop, green = gain)", "municipality_labels": labels,
    }, ensure_ascii=False, indent=2) + "\n")

    # 2. forest share map
    def forest_class(r):
        cover = float(r["cover_frac"])
        if cover == 0:
            return 0
        if cover < 0.95:
            return 1
        return 2 + int(np.digitize(float(r["forest_frac"]), FOREST_BREAKS))

    fcls = grid_array(records, grid, forest_class)
    fcolours = ["#ffffff", "#bdbdbd", *plt.get_cmap("Greens")(np.linspace(0.2, 0.9, len(FOREST_BREAKS) + 1))]
    fnames = ["分類図と交差なし", "分類図の覆い95%未満", "森林率 0.5 未満", "0.5 〜 0.8", "0.8 〜 0.9", "0.9 以上"]
    fcounts = [int(np.sum(fcls == i)) for i in range(len(fcolours))]
    fig, ax = plt.subplots(figsize=(11, 8.6), constrained_layout=True)
    patch = draw_base(ax, munis, extent, mid_lat)
    ax.imshow(fcls, extent=extent, origin="upper", interpolation="nearest", zorder=2,
              cmap=ListedColormap(fcolours), norm=BoundaryNorm(np.arange(-0.5, len(fcolours)), len(fcolours)))
    draw_boundaries(ax, munis, patch)
    label_municipalities(ax, munis, extent)
    handles = [Patch(facecolor=c, edgecolor="#888888", label=f"{n} ({fcounts[i]:,})")
               for i, (c, n) in enumerate(zip(fcolours, fnames))]
    handles.reverse()
    ax.legend(handles=handles, title="ForTy 2020年 クラス1〜3 の面積率", loc="upper left", bbox_to_anchor=(1.01, 1),
              fontsize=8, title_fontsize=8.5, framealpha=0.95)
    ax.set(xlabel="経度 (度)", ylabel="緯度 (度)", title="北海道東部 集計面ごとの森林率 (ForTy 2020年)")
    fig.text(0.5, -0.01, footer, ha="center", fontsize=8)
    fig.savefig(OUTPUT / "forest-map.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    (OUTPUT / "forest-map.json").write_text(json.dumps({
        "question": "分類図はどこを覆い、覆う面のどこが森林率の主条件 (0.8) を満たすか",
        **common, "value": "forest_frac = ForTy class 1-3 area / cell area, shown only where cover_frac >= 0.95",
        "kind": "rate", "breaks": FOREST_BREAKS, "breaks_reason": "the thresholds compared in the analysis",
        "classes": fnames, "class_counts": fcounts,
    }, ensure_ascii=False, indent=2) + "\n")

    # 3. candidate cells
    main_ids = [(i["cell_row"], i["cell_col"]) for i in summary["variants"]["forest_0_8_main"]]
    stable = {(i["cell_row"], i["cell_col"]) for i in summary["stable_main_ids"]}
    raw_only = [(i["cell_row"], i["cell_col"]) for i in summary["variants"]["raw"] if
                (i["cell_row"], i["cell_col"]) not in set(main_ids)]
    elig = grid_array(records, grid, lambda r: 1.0 if eligible(r) else None)
    n_elig = int(np.nansum(elig))
    if n_elig != summary["cells_eligible_main"]:
        raise ValueError(f"eligible cells {n_elig} != summary {summary['cells_eligible_main']}")
    style = {"stable": ("#8e2675", 2.0), "main": ("#157f9b", 2.0), "raw": ("#b45f06", 1.6)}

    def draw_candidates(ax, view, fontsize):
        patch = draw_base(ax, munis, view, mid_lat)
        ax.imshow(elig, extent=extent, origin="upper", interpolation="nearest", zorder=2,
                  cmap=ListedColormap(["#a9a9a9"]), vmin=0, vmax=2)
        draw_boundaries(ax, munis, patch)
        for rank, cid in enumerate(main_ids, 1):
            x, y, s = cell_box(grid, *cid)
            colour, lw = style["stable" if cid in stable else "main"]
            ax.add_patch(Rectangle((x, y), s, s, facecolor=colour, edgecolor=colour, linewidth=lw, zorder=7))
            ax.annotate(str(rank), (x + s, y + s), xytext=(2, 2), textcoords="offset points", fontsize=fontsize,
                        color=colour, fontweight="bold", zorder=8, annotation_clip=True,
                        bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.85})
        for cid in raw_only:
            x, y, s = cell_box(grid, *cid)
            colour, lw = style["raw"]
            ax.add_patch(Rectangle((x, y), s, s, facecolor="none", edgecolor=colour, linewidth=lw, zorder=7))

    fig, ax = plt.subplots(figsize=(11, 8.6), constrained_layout=True)
    draw_candidates(ax, extent, 7.5)
    label_municipalities(ax, munis, extent)
    zoom = [144.105, 144.185, 43.44, 43.515]
    inset = ax.inset_axes([0.68, 0.1, 0.29, 0.36])
    inset.set_zorder(10)
    draw_candidates(inset, zoom, 9)
    inset.set_xlim(zoom[0], zoom[1])
    inset.set_ylim(zoom[2], zoom[3])
    inset.set_xticks([])
    inset.set_yticks([])
    ax.indicate_inset_zoom(inset, edgecolor="#333333")
    handles = [
        Patch(facecolor=style["stable"][0], label=f"設定を変えても残る ({len(stable)})"),
        Patch(facecolor=style["main"][0], label=f"主条件のみ ({len(main_ids) - len(stable)})"),
        Patch(facecolor="none", edgecolor=style["raw"][0], linewidth=1.6, label=f"生の上位のみ ({len(raw_only)})"),
        Patch(facecolor="#a9a9a9", label=f"主母集団 ({n_elig:,})"),
        Patch(facecolor="none", edgecolor="#4d4d4d", label="市町村境界"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, framealpha=0.95,
              title="数字は主条件の順位", title_fontsize=8.5)
    ax.set(xlabel="経度 (度)", ylabel="緯度 (度)", title="北海道東部 現地照合候補の集計面")
    fig.text(0.5, -0.01, footer, ha="center", fontsize=8)
    fig.savefig(OUTPUT / "candidate-cells-map.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    (OUTPUT / "candidate-cells-map.json").write_text(json.dumps({
        "question": "主条件の上位20面と生の上位のみの面は、どの市町村のどこにあるか",
        **common, "counts": {"stable": len(stable), "main_other": len(main_ids) - len(stable),
                             "raw_only": len(raw_only), "eligible": n_elig},
        "ranks": "number beside each square = rank in forest_0_8_main",
        "inset_extent": zoom,
    }, ensure_ascii=False, indent=2) + "\n")
    by_id = {(r["cell_row"], r["cell_col"]): r for r in records}
    with (OUTPUT / "candidate-municipalities.csv").open("w", newline="") as fh:
        out = csv.writer(fh, lineterminator="\n")
        out.writerow(["rank_main", "group", "cell_row", "cell_col", "lon", "lat", "drop", "forest_frac", "municipality"])
        rows = [(rank, "stable" if cid in stable else "main_only", cid) for rank, cid in enumerate(main_ids, 1)]
        rows += [("", "raw_only", cid) for cid in raw_only]
        for rank, group, cid in rows:
            r = by_id[cid]
            name = municipality_of(float(r["lon"]), float(r["lat"]), munis)
            if not name:
                raise ValueError(f"cell centre {cid} falls in no municipality")
            out.writerow([rank, group, *cid, f"{float(r['lon']):.4f}", f"{float(r['lat']):.4f}",
                          f"{float(r['drop']):.2f}", f"{float(r['forest_frac']):.3f}", name])
    print(json.dumps({"font": font, "cells": len(records), "municipalities": len(munis)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

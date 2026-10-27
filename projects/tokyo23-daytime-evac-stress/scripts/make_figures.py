"""Draw the two figures for the daytime evacuation-stress report.

fig1: night vs daytime population per shelter (log/symlog scatter), top-20 lists highlighted.
fig2: map of the absolute increase in people per shelter (Delta), top 10 numbered, zero-shelter meshes marked.

Run: ~/.venvs/geoai/bin/python scripts/make_figures.py
"""

import importlib.util
import json
import warnings
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.colors import SymLogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import matplotlib.patheffects as pe
from shapely import make_valid, wkt
from shapely.geometry import MultiPolygon, Polygon

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
ART = ROOT / "artifacts" / "tokyo23-daytime-evac-stress"
OUT = PROJECT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

FONT_HELPER = ROOT / ".agents/skills/analysis-visualize/scripts/cjk_font.py"
spec = importlib.util.spec_from_file_location("cjk_font", FONT_HELPER)
CJK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CJK)
use_cjk_font = CJK.use_cjk_font

ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
CRS_NOTE = "EPSG:6677 (JGD2011 / 平面直角座標第 IX 系) に投影して描画"


def polygons_from_wkt(text):
    g = make_valid(wkt.loads(text))
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]


def load_shapes():
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET geometry_always_xy = true;")
    wards = con.sql(f"""
        select code5, name, rep_lon, rep_lat,
               ST_AsText(ST_Transform(geometry, 'EPSG:6677')) wkt
        from read_parquet('{ADMIN}') where code5 between '13101' and '13123'
    """).fetchall()
    mesh = con.sql(f"""
        select mesh1kmid,
               ST_AsText(ST_Transform(ST_SetCRS(ST_MakeEnvelope(
                   lon_min, lat_min, lon_min + 1.0/80.0, lat_min + 1.0/120.0), 'OGC:CRS84'),
                 'EPSG:6677')) wkt,
               ST_X(ST_Transform(ST_SetCRS(ST_Point(
                   lon_min + 0.5/80.0, lat_min + 0.5/120.0), 'OGC:CRS84'), 'EPSG:6677')) x,
               ST_Y(ST_Transform(ST_SetCRS(ST_Point(
                   lon_min + 0.5/80.0, lat_min + 0.5/120.0), 'OGC:CRS84'), 'EPSG:6677')) y
        from (
          select mesh1kmid,
                 (cast(substr(mesh1kmid,3,2) as int) + 100)
                   + cast(substr(mesh1kmid,6,1) as int) * 7.5/60
                   + cast(substr(mesh1kmid,8,1) as int) * 45/3600 as lon_min,
                 cast(substr(mesh1kmid,1,2) as int) / 1.5
                   + cast(substr(mesh1kmid,5,1) as int) * 5/60
                   + cast(substr(mesh1kmid,7,1) as int) * 30/3600 as lat_min
          from read_parquet('{ART / "mesh_dataset.parquet"}')
        )
    """).fetchall()
    # ward label points
    lab = con.sql(f"""
        select name,
               ST_X(ST_Transform(ST_SetCRS(ST_Point(rep_lon, rep_lat), 'EPSG:4612'), 'EPSG:6677')) x,
               ST_Y(ST_Transform(ST_SetCRS(ST_Point(rep_lon, rep_lat), 'EPSG:4612'), 'EPSG:6677')) y
        from read_parquet('{ADMIN}') where code5 between '13101' and '13123'
    """).fetchall()
    return wards, mesh, lab


def fig_scatter(mesh):
    f = mesh[mesh.sh_1000 > 0].copy()
    f["nr"] = f.night / f.sh_1000
    f["dr"] = f.day19 / f.sh_1000
    day_top = f.sort_values(["dr", "mesh1kmid"], ascending=[False, True]).head(20)
    night_top = f.sort_values(["nr", "mesh1kmid"], ascending=[False, True]).head(20)
    worst = f.sort_values(["dr", "mesh1kmid"], ascending=[False, True]).iloc[0]
    ntop = night_top.iloc[0]

    title = "夜の人口/避難所と昼の人口/避難所は、上位で入れ替わる"
    xlabel = "夜間の人口/避難所 (人/件、2020年国勢調査)"
    ylabel = "昼間の人口/避難所 (人/件、2019年10月平日)"
    font = use_cjk_font(" ".join([title, xlabel, ylabel, "夜間上位20", "昼間上位20",
                                  "全メッシュ", "等しい線", "夜間上位", "昼間上位",
                                  "昼間1位", "夜間1位", "人", "夜", "昼", "→", "/件",
                                  "夜間の人口/避難所の順位は、昼間の順位を予測するか",
                                  "(1 km メッシュ、中心から1 km 圏内の指定避難所。点は1件の避難所あたり)",
                                  "夜間0の5メッシュは左端。等しい線は y=x。",
                                  "出典: 国勢調査2020・全国人流オープンデータ2019-10・指定避難所2026-10-06",
                                  "Spearman 0.399。上位20の重なりは1/20。"]
                                 + list(mesh.ward.dropna().unique())))

    fig, ax = plt.subplots(figsize=(8.6, 7.4))
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yscale("symlog", linthresh=10)
    ax.plot([0, 100000], [0, 100000], color="#888888", lw=1, ls="--", zorder=1)
    ax.scatter(f.nr, f.dr, s=18, color="#9e9e9e", alpha=0.45, linewidths=0, zorder=2,
               label="全メッシュ (n=578)")
    ax.scatter(night_top.nr, night_top.dr, s=70, facecolors="none", edgecolors="#0072B2",
               linewidths=1.6, zorder=4, label="夜間上位20")
    ax.scatter(day_top.nr, day_top.dr, s=44, color="#D55E00", zorder=5, label="昼間上位20")

    ax.annotate(f"昼間1位 {worst.mesh1kmid}\n{worst.ward} 夜 {worst.night:,.0f} 人/件 → 昼 {worst.day19:,.0f} 人/件",
                (worst.nr, worst.dr), xytext=(46, -62), textcoords="offset points",
                fontsize=9, color="#8a3b00",
                arrowprops=dict(arrowstyle="-", color="#8a3b00", lw=0.8, shrinkB=5),
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#D55E00", alpha=0.9))
    ax.annotate(f"夜間1位 {ntop.mesh1kmid}\n{ntop.ward} 夜 {ntop.night:,.0f} 人/件",
                (ntop.nr, ntop.dr), xytext=(48, -92), textcoords="offset points",
                fontsize=9, color="#005a8c",
                arrowprops=dict(arrowstyle="-", color="#0072B2", lw=0.8, shrinkB=5,
                                connectionstyle="arc3,rad=0.2"),
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#0072B2", alpha=0.9))

    ax.set_xlim(0, 20000)
    ax.set_ylim(0, 200000)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title + "\n(1 km メッシュ、中心から1 km 圏内の指定避難所。点は1件の避難所あたり)")
    ax.grid(alpha=0.2, which="both")
    ax.legend(loc="lower right", fontsize=9)
    fig.text(0.01, 0.01,
             "Spearman 0.399。上位20の重なりは1/20。夜間0の5メッシュは左端。"
             "等しい線は y=x。出典: 国勢調査2020・全国人流オープンデータ2019-10・指定避難所2026-10-06",
             fontsize=8, ha="left")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUT / "fig1_night_vs_day_ratio.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    meta = {
        "figure": "fig1_night_vs_day_ratio.png",
        "question": "夜間の人口/避難所の順位は、昼間の順位を予測するか",
        "source_output": "outputs/analysis_results.json, artifacts/.../mesh_dataset.parquet",
        "n": int(len(f)),
        "zero_night_meshes": int((f.nr == 0).sum()),
        "highlighted": {"day_top20_overlap_night": int(len(set(day_top.mesh1kmid) & set(night_top.mesh1kmid)))},
        "data_versions": {
            "census": "estat-census-mesh-2020@6c486c8 (2020-10-01)",
            "flow": "mlit-1km-fromto-2022-01@2424a9d (2019-10)",
            "shelters": "gsi-evacuation-sites-jp@d8ad216 (2026-10-06)",
        },
        "axes": "symlog (linthresh=10) both axes; x 0-20,000; y 0-200,000",
        "font": font,
    }
    (OUT / "fig1_night_vs_day_ratio.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n")


def fig_map(mesh, wards, mesh_shapes, lab):
    f = mesh[mesh.sh_1000 > 0].copy()
    f["delta"] = f.day19 / f.sh_1000 - f.night / f.sh_1000
    top10 = f.sort_values(["delta", "mesh1kmid"], ascending=[False, True]).head(10)
    zero = mesh[mesh.sh_1000 == 0].copy()
    top10_ids = list(top10.mesh1kmid)

    shapes = {mid: polygons_from_wkt(w) for mid, w, x, y in mesh_shapes}
    xs = {mid: x for mid, w, x, y in mesh_shapes}
    ys = {mid: y for mid, w, x, y in mesh_shapes}

    title = "昼間に避難所1件あたりの負担が増える場所"
    cbar_label = "昼間−夜間の人口/避難所 (人/件)"
    font = use_cjk_font(" ".join([title, cbar_label, "23区の境界", "施設立地なし (分母0)",
                                  "上位10", "増加", "減少", "図3で拡大", "拡大",
                                  "増加 (昼が夜より多い)", "減少 (夜が昼より多い)",
                                  "1 km 圏内に避難所なし (分母0、55)",
                                  "1 km メッシュ、指定避難所、2019年10月平日昼 − 2020年夜",
                                  "色は対称ログ (0 の前後で 1,000 人/件を線形)。"
                                  "増加の上位1を注記し、上位10は破線の範囲を図3で拡大。",
                                  "昼 人 / 避難所 件",
                                  "−3,000 −1,000 0 1,000 10,000 100,000"]
                                 + [n for n, _, _ in lab]))

    fig, ax = plt.subplots(figsize=(9.2, 9.6))
    for code5, name, lon, lat, text in wards:
        for p in polygons_from_wkt(text):
            ax.plot(*p.exterior.xy, color="#555555", lw=0.5, zorder=1)

    norm = SymLogNorm(linthresh=1000, vmin=-4000, vmax=100000, base=10)
    vals = f.delta.to_numpy()
    polys = [shapes[mid] for mid in f.mesh1kmid]
    # PolyCollection wants one list of rings per item; draw each mesh square separately by flattening.
    all_polys, all_vals = [], []
    for mid, v in zip(f.mesh1kmid, vals):
        for p in shapes[mid]:
            all_polys.append(np.asarray(p.exterior.coords))
            all_vals.append(v)
    coll = PolyCollection(all_polys, array=np.array(all_vals), cmap="coolwarm", norm=norm,
                          edgecolors="none", zorder=2)
    ax.add_collection(coll)

    # zero-shelter meshes: ratio undefined
    zx = [xs[m] for m in zero.mesh1kmid]
    zy = [ys[m] for m in zero.mesh1kmid]
    ax.scatter(zx, zy, marker="x", s=24, color="#222222", linewidths=1.2, zorder=4)

    for name, x, y in lab:
        ax.annotate(name, (x, y), ha="center", va="center", fontsize=7, color="#333333",
                    zorder=7, path_effects=[pe.withStroke(linewidth=2, foreground="white")])

    # top-10 all sit in the central business core; number them in a zoom panel, mark the
    # overview with the single worst mesh and the extent of the zoom.
    top1 = top10.iloc[0]
    ax.annotate(f"1  {top1.mesh1kmid} {top1.ward}\n昼 {top1.day19:,.0f} 人 / 避難所 {top1.sh_1000} 件",
                (xs[top1.mesh1kmid], ys[top1.mesh1kmid]), xytext=(36, 128),
                textcoords="offset points", fontsize=9, color="#7a1f1f",
                arrowprops=dict(arrowstyle="->", color="#7a1f1f", lw=1.0,
                                connectionstyle="arc3,rad=-0.25", shrinkB=4),
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#7a1f1f", alpha=0.95),
                zorder=8)

    rx0, ry0, rx1, ry1 = zoom_rect(f, shapes, xs, ys)
    ax.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0, fill=False, edgecolor="black",
                           lw=1.1, ls="--", zorder=6))

    cb = fig.colorbar(coll, ax=ax, shrink=0.62, pad=0.02)
    cb.set_label(cbar_label)
    cb.set_ticks([-3000, -1000, 0, 1000, 10000, 100000])
    cb.ax.set_yticklabels(["−3,000", "−1,000", "0", "1,000", "10,000", "100,000"])

    handles = [Patch(facecolor="#b2182b", label="増加 (昼が夜より多い)"),
               Patch(facecolor="#2166ac", label="減少 (夜が昼より多い)"),
               Line2D([0], [0], marker="x", color="#222222", lw=0, markersize=7,
                      label="1 km 圏内に避難所なし (分母0、55)")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.028),
               ncol=3, fontsize=8, frameon=False)
    ax.set_title(title + "\n(1 km メッシュ、指定避難所、2019年10月平日昼 − 2020年夜)")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(0.01, 0.004, CRS_NOTE + "。色は対称ログ (0 の前後で 1,000 人/件を線形)。"
             "増加の上位1を注記し、上位10は破線の範囲を図3で拡大。", fontsize=8)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUT / "fig2_delta_map.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    meta = {
        "figure": "fig2_delta_map.png",
        "question": "昼間に避難所1件あたりの負担が最も増えるメッシュはどこか",
        "source_output": "artifacts/.../mesh_dataset.parquet; outputs/top20_delta_abs.csv",
        "n_colored": int(len(f)),
        "n_zero_undefined": int(len(zero)),
        "top1": top10.iloc[0][["mesh1kmid", "ward", "night", "day19", "sh_1000", "delta"]]
        .to_dict(),
        "top10": top10[["mesh1kmid", "ward", "night", "day19", "sh_1000", "delta"]]
        .to_dict(orient="records"),
        "zoom_panel": "fig3_zoom_top10.png",
        "classes": "SymLogNorm(linthresh=1000, vmin=-4000, vmax=100000)",
        "crs": "EPSG:6677",
        "data_versions": {
            "census": "estat-census-mesh-2020@6c486c8",
            "flow": "mlit-1km-fromto-2022-01@2424a9d",
            "shelters": "gsi-evacuation-sites-jp@d8ad216",
            "wards": "jp-admin-2026-09@e6c87b1",
        },
        "font": font,
    }
    (OUT / "fig2_delta_map.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return (rx0, ry0, rx1, ry1)


ZOOM_LON = (139.685, 139.785)
ZOOM_LAT = (35.605, 35.745)
WARD_OFFSETS = {
    "千代田区": (-46, 34), "中央区": (10, 26), "港区": (-44, -34),
    "新宿区": (-52, 16), "豊島区": (-44, 30), "品川区": (30, 16),
    "文京区": (-8, 30), "台東区": (-26, 18), "目黒区": (-38, -24),
    "渋谷区": (-44, 12), "江東区": (52, 10), "墨田区": (44, 26),
}


def zoom_rect(f, shapes, xs, ys):
    sel = f[(f.lon >= ZOOM_LON[0]) & (f.lon <= ZOOM_LON[1])
            & (f.lat >= ZOOM_LAT[0]) & (f.lat <= ZOOM_LAT[1])]
    bounds = [p.bounds for mid in sel.mesh1kmid for p in shapes[mid]]
    pad = 500.0
    return (min(b[0] for b in bounds) - pad, min(b[1] for b in bounds) - pad,
            max(b[2] for b in bounds) + pad, max(b[3] for b in bounds) + pad)


def fig_zoom(mesh, wards, mesh_shapes, lab, rect):
    f = mesh[mesh.sh_1000 > 0].copy()
    f["delta"] = f.day19 / f.sh_1000 - f.night / f.sh_1000
    top10 = f.sort_values(["delta", "mesh1kmid"], ascending=[False, True]).head(10)
    zero = mesh[mesh.sh_1000 == 0].copy()

    shapes = {mid: polygons_from_wkt(w) for mid, w, x, y in mesh_shapes}
    xs = {mid: x for mid, w, x, y in mesh_shapes}
    ys = {mid: y for mid, w, x, y in mesh_shapes}

    x0, y0, x1, y1 = rect
    inside = ((f.lon >= ZOOM_LON[0]) & (f.lon <= ZOOM_LON[1])
              & (f.lat >= ZOOM_LAT[0]) & (f.lat <= ZOOM_LAT[1]))
    inner = f[inside]

    title = "増加の上位10メッシュ (中心部の拡大)"
    cbar_label = "昼間−夜間の人口/避難所 (人/件)"
    font = use_cjk_font(" ".join([title, cbar_label, "1 km 圏内に避難所なし (分母0)",
                                  "増加の上位10 (番号は表と対応)",
                                  "1 km メッシュ、指定避難所、2019年10月平日昼 − 2020年夜",
                                  "色は対称ログ (0 の前後で 1,000 人/件を線形)。",
                                  "−3,000 −1,000 0 1,000 10,000 100,000"]
                                 + [n for n, _, _ in lab]))

    fig, ax = plt.subplots(figsize=(7.8, 9.6))
    for code5, name, lon, lat, text in wards:
        for p in polygons_from_wkt(text):
            ax.plot(*p.exterior.xy, color="#555555", lw=0.6, zorder=1)

    norm = SymLogNorm(linthresh=1000, vmin=-4000, vmax=100000, base=10)
    all_polys, all_vals = [], []
    for mid in inner.mesh1kmid:
        for p in shapes[mid]:
            all_polys.append(np.asarray(p.exterior.coords))
            all_vals.append(float(inner.loc[inner.mesh1kmid == mid, "delta"].iloc[0]))
    coll = PolyCollection(all_polys, array=np.array(all_vals), cmap="coolwarm", norm=norm,
                          edgecolors="white", linewidths=0.5, zorder=2)
    ax.add_collection(coll)

    zin = zero[(zero.lon >= ZOOM_LON[0]) & (zero.lon <= ZOOM_LON[1])
               & (zero.lat >= ZOOM_LAT[0]) & (zero.lat <= ZOOM_LAT[1])]
    ax.scatter([xs[m] for m in zin.mesh1kmid], [ys[m] for m in zin.mesh1kmid],
               marker="x", s=26, color="#222222", linewidths=1.1, zorder=4)

    for i, row in enumerate(top10.itertuples(), start=1):
        ax.scatter(xs[row.mesh1kmid], ys[row.mesh1kmid], s=175, color="white",
                   edgecolors="black", linewidths=1.1, zorder=6)
        ax.annotate(str(i), (xs[row.mesh1kmid], ys[row.mesh1kmid]), ha="center", va="center",
                    fontsize=10, fontweight="bold", color="black", zorder=7,
                    path_effects=[pe.withStroke(linewidth=1.2, foreground="white")])

    for name, x, y in lab:
        if x0 <= x <= x1 and y0 <= y <= y1:
            ax.annotate(name, (x, y), xytext=WARD_OFFSETS.get(name, (0, 0)),
                        textcoords="offset points", ha="center", va="center",
                        fontsize=8, color="#333333", zorder=5,
                        path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])

    cb = fig.colorbar(coll, ax=ax, shrink=0.55, pad=0.02)
    cb.set_label(cbar_label)
    cb.set_ticks([-3000, -1000, 0, 1000, 10000, 100000])
    cb.ax.set_yticklabels(["−3,000", "−1,000", "0", "1,000", "10,000", "100,000"])

    fig.legend(handles=[Line2D([0], [0], marker="o", color="white", markeredgecolor="black",
                              lw=0, markersize=9, label="増加の上位10 (番号は表と対応)"),
                       Line2D([0], [0], marker="x", color="#222222", lw=0, markersize=7,
                              label="1 km 圏内に避難所なし (分母0)")],
              loc="lower center", bbox_to_anchor=(0.5, 0.028), ncol=2,
              fontsize=8, frameon=False)
    ax.set_title(title + "\n(1 km メッシュ、指定避難所、2019年10月平日昼 − 2020年夜)")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(0.01, 0.004, CRS_NOTE + "。色は対称ログ (0 の前後で 1,000 人/件を線形)。"
             "× は 1 km 圏内に避難所なし。番号は表の順位に対応。", fontsize=8)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUT / "fig3_zoom_top10.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    meta = {
        "figure": "fig3_zoom_top10.png",
        "question": "増加の上位10メッシュは、中心部のどこにあるか",
        "source_output": "artifacts/.../mesh_dataset.parquet; outputs/top20_delta_abs.csv",
        "n_colored_in_view": int(len(inner)),
        "top10": top10[["mesh1kmid", "ward", "night", "day19", "sh_1000", "delta"]]
        .to_dict(orient="records"),
        "extent_epsg6677": [float(x0), float(x1), float(y0), float(y1)],
        "classes": "SymLogNorm(linthresh=1000, vmin=-4000, vmax=100000)",
        "crs": "EPSG:6677",
        "data_versions": {
            "census": "estat-census-mesh-2020@6c486c8",
            "flow": "mlit-1km-fromto-2022-01@2424a9d",
            "shelters": "gsi-evacuation-sites-jp@d8ad216",
            "wards": "jp-admin-2026-09@e6c87b1",
        },
        "font": font,
    }
    (OUT / "fig3_zoom_top10.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n")


def main():
    mesh = pd.read_parquet(ART / "mesh_dataset.parquet")
    wards, mesh_shapes, lab = load_shapes()
    fig_scatter(mesh)
    rect = fig_map(mesh, wards, mesh_shapes, lab)
    fig_zoom(mesh, wards, mesh_shapes, lab, rect)
    print("wrote", OUT / "fig1_night_vs_day_ratio.png", OUT / "fig2_delta_map.png",
          OUT / "fig3_zoom_top10.png")


if __name__ == "__main__":
    main()

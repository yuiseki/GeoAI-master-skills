"""Risk maps on a 100 m grid that a reader can place: the cells drawn as their squares, frozen background
boundaries and names, the legend outside the map with the number of cells per class, a caption with the
versions, a check of the number of cells drawn, and a count of overlapping texts.

Built on the analysis-visualize skill's context_map.py (background areas, area names, text overlaps). The cells
are not drawn one polygon each (a million patches): the grid is a raster in a projected CRS, so imshow with the
grid's extent draws every cell as its exact square.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../../.agents/skills/analysis-visualize/scripts"))
import context_map as cm  # noqa: E402

ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
ADMIN_SOURCE = "市町村界 jp-admin-2026-09 (e6c87b1、2020 年国勢調査の面)"
OSM_POINT = "hf://datasets/yuiseki/osm-japan-src-2026-08@9a9b4a77e89e28a66bf15781644a16b63501f622/parquet/planet_osm_point.parquet"
OSM_SOURCE = "地名 OpenStreetMap (osm-japan-src-2026-08、2026-08-31)"
CRS_NOTE = "背景の JGD2000 (EPSG:4612) と格子の JGD2011 系の差は約 1 m で、図の線の幅より小さい"
CLASSES = [("上位 1%", 0.01), ("上位 1〜5%", 0.05), ("上位 5〜10%", 0.10), ("上位 10〜25%", 0.25), ("上位 25〜50%", 0.50), ("下位 50%", 1.0)]
COLOURS = ["#9b0a19", "#e5543b", "#f59e72", "#facba6", "#fde0c5", "#f6f4f0"]


def rank_classes(score):
    """0 (top 1%) .. 5 (bottom half) by the rank of the score among the cells."""
    n = len(score)
    share = np.empty(n)
    share[np.argsort(-np.asarray(score), kind="stable")] = (np.arange(n) + 1) / n
    return np.searchsorted([b for _, b in CLASSES][:-1], share, side="left")


def to_crs(geom, src, dst):
    import pyproj
    import shapely

    tr = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    return shapely.transform(geom, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))


def lonlat_view(view, crs, pad=0.0):
    import pyproj
    import shapely

    tr = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    x0, x1, y0, y1 = view
    lon, lat = tr.transform([x0, x0, x1, x1], [y0, y1, y0, y1])
    return shapely.box(min(lon) - pad, min(lat) - pad, max(lon) + pad, max(lat) + pad)


def without_holes(geom):
    """The polygon or multipolygon with its interior rings dropped.

    The census-based municipal areas have many small holes (gaps in the small areas); their outlines, drawn over the
    cells, read as a scatter of dark dots that can be taken for reports. An enclave keeps its outline, drawn as its
    own area.
    """
    import shapely

    if geom.geom_type == "Polygon":
        return shapely.Polygon(geom.exterior)
    if geom.geom_type == "MultiPolygon":
        return shapely.MultiPolygon([shapely.Polygon(p.exterior) for p in geom.geoms])
    return geom


def background(view, crs, pref_code):
    """(all areas in the view, the prefecture's areas) as (name, geometry) in the grid CRS, without holes."""
    box = lonlat_view(view, crs, pad=0.05)
    areas = cm.read_areas(ADMIN, "name", "ward is null", box)
    pref = {n for n, _ in cm.read_areas(ADMIN, "name", f"ward is null and pref_code = '{pref_code}'", box)}
    moved = [(n, without_holes(to_crs(g, "EPSG:4612", crs))) for n, g in areas]
    return moved, [(n, g) for n, g in moved if n in pref]


def place_names(view, crs, kinds=("city", "town", "village", "suburb", "quarter")):
    """OSM place points (name, x, y) in the view."""
    import duckdb
    import pyproj

    box = lonlat_view(view, crs)
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, y0 = tr.transform(box.bounds[0], box.bounds[1])
    x1, y1 = tr.transform(box.bounds[2], box.bounds[3])
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs")
    kl = ",".join(f"'{k}'" for k in kinds)
    rows = con.sql(f"""select name, place, ST_X(way), ST_Y(way) from read_parquet('{OSM_POINT}')
                       where bbox.xmin <= {x1} and bbox.xmax >= {x0} and bbox.ymin <= {y1} and bbox.ymax >= {y0}
                         and place in ({kl}) and name is not null""").fetchall()
    back = pyproj.Transformer.from_crs("EPSG:3857", crs, always_xy=True)
    out = []
    for name, kind, x, y in rows:
        px, py = back.transform(x, y)
        if view[0] <= px <= view[1] and view[2] <= py <= view[3]:
            out.append((name, kind, px, py))
    return out


def thin_labels(fig, prioritised, keep_clear=()):
    """Keep labels in order of priority (lower first) where they do not overlap a kept label or a kept-clear box.

    prioritised: (priority, text). Returns (kept texts, number hidden). Hidden texts are made invisible.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    clear = [b.get_window_extent(r) for b in keep_clear]
    kept, boxes, dropped = [], [], 0
    for _, t in sorted(prioritised, key=lambda pt: pt[0]):
        bb = t.get_window_extent(r)
        if any(bb.overlaps(o) for o in boxes + clear):
            t.set_visible(False)
            dropped += 1
            continue
        kept.append(t)
        boxes.append(bb)
    return kept, dropped


def draw_cells(ax, classes_arr, grid):
    from matplotlib.colors import ListedColormap

    extent = [grid["x0"], grid["x0"] + grid["nx"] * grid["size"], grid["y0"], grid["y0"] + grid["ny"] * grid["size"]]
    ax.imshow(np.ma.masked_less(classes_arr, 0), origin="lower", extent=extent, cmap=ListedColormap(COLOURS),
              vmin=-0.5, vmax=len(COLOURS) - 0.5, interpolation="nearest", zorder=2)


def legend_handles(counts, extra=()):
    from matplotlib.patches import Patch

    hs = [Patch(facecolor=c, edgecolor="#4d4d4d", lw=0.4, label=f"{lab} ({n:,} セル)") for (lab, _), c, n in zip(CLASSES, COLOURS, counts)]
    return hs + list(extra)


def finish(ax, view, crs="EPSG:6678"):
    ax.set_xlim(view[0], view[1])
    ax.set_ylim(view[2], view[3])
    ax.set_aspect(cm.aspect(crs, view[2], view[3]))
    ax.set_xticks([])
    ax.set_yticks([])

"""Overlay Tokyo 23-ward underpass inventories, OSM roads, GSI elevation and flood layers.

Run from this project with:
  uvx --from 'duckdb>=1.5.5' --with numpy --with matplotlib --with shapely --with pyproj --with rasterio \
    python scripts/08_map_tokyo23_flood_context.py

Downloaded inputs and GSI tiles stay under ignored artifacts/_flood/underpass-ponding-exposure/map-context/.
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pyproj import Transformer
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union
from rasterio.features import rasterize
from rasterio.transform import from_origin
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
ART = ROOT / "artifacts/_flood/underpass-ponding-exposure/map-context"
OUT = ROOT / "projects/_flood/underpass-ponding-exposure/outputs"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
UNDERPASS = "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet"
KANSUI = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet"
A31A = "hf://datasets/yuiseki/ksj-a31a-flood-tokyo23@5b2259273128d0b79b491eb758abe0db67c4feac/parquet/flood_area.parquet"
OSM = "hf://datasets/yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664/parquet/planet_osm_line.parquet"
FLOOD_RECORDS = "hf://datasets/yuiseki/tokyo-flood-record-jp@354b0d9f8030347192eaa387500f60da76c07e1a/parquet/flood_point.parquet"
DEM_Z = 14  # GSI DEM10B, about 10 m ground sampling
DEM_LAYER = "dem"
TILE_SIZE = 256
RADIUS = 6_378_137.0
TILE_CACHE = ART / "dem" / str(DEM_Z)
WEBMERCATOR_LIMIT = math.pi * RADIUS
DEPTH_LABELS = {
    1: "0–0.5 m", 2: "0.5–3 m", 3: "3–5 m",
    4: "5–10 m", 5: "10–20 m", 6: "20 m以上",
}
DEPTH_COLORS = {
    1: "#deebf7", 2: "#9ecae1", 3: "#6baed6",
    4: "#4292c6", 5: "#2171b5", 6: "#084594",
}


def depth_label(class_code: int) -> str:
    try:
        return DEPTH_LABELS[int(class_code)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"unknown A31a maximum-depth class: {class_code}") from exc


def remove_zero_area_holes(geometry: dict) -> dict:
    """Discard known zero-area boundary seams without removing real holes."""
    geom = shape(geometry)
    polygons = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    clean = [Polygon(p.exterior.coords, [r.coords for r in p.interiors if Polygon(r).area > 0.01])
             for p in polygons if p.geom_type == "Polygon"]
    if geom.geom_type == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": [mapping_polygon(p) for p in clean]}
    if not clean:
        return {"type": "Polygon", "coordinates": []}
    return {"type": "Polygon", "coordinates": mapping_polygon(clean[0])}


def mapping_polygon(poly: Polygon) -> list:
    return [list(poly.exterior.coords), *[list(r.coords) for r in poly.interiors]]


def _polygons(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for part in geom.geoms for p in _polygons(part)]
    return []


def _geojson(geometry) -> dict:
    return json.loads(geometry)


def _fetch_tile(x: int, y: int) -> Path:
    TILE_CACHE.mkdir(parents=True, exist_ok=True)
    path = TILE_CACHE / f"{x}_{y}.txt"
    missing = TILE_CACHE / f"{x}_{y}.404"
    if path.exists() or missing.exists():
        return path
    url = f"https://cyberjapandata.gsi.go.jp/xyz/{DEM_LAYER}/{DEM_Z}/{x}/{y}.txt"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
        path.write_bytes(payload)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        missing.write_bytes(b"")
    time.sleep(0.12)
    return path


def _dem_mosaic(bounds_3857: tuple[float, float, float, float]):
    xmin, ymin, xmax, ymax = bounds_3857
    n = 2**DEM_Z
    tile_span = 2 * WEBMERCATOR_LIMIT / n
    tx0 = max(0, int(math.floor((xmin + WEBMERCATOR_LIMIT) / tile_span)))
    tx1 = min(n - 1, int(math.floor((xmax + WEBMERCATOR_LIMIT) / tile_span)))
    ty0 = max(0, int(math.floor((WEBMERCATOR_LIMIT - ymax) / tile_span)))
    ty1 = min(n - 1, int(math.floor((WEBMERCATOR_LIMIT - ymin) / tile_span)))
    mosaic = np.full(((ty1 - ty0 + 1) * TILE_SIZE, (tx1 - tx0 + 1) * TILE_SIZE), np.nan)
    from dem import parse_tile

    counts = {"requested": 0, "available": 0, "missing_404": 0}
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            counts["requested"] += 1
            path = _fetch_tile(tx, ty)
            if path.exists():
                arr = parse_tile(path.read_text())
                if arr.shape != (TILE_SIZE, TILE_SIZE):
                    raise ValueError(f"unexpected GSI tile shape {arr.shape}: {path}")
                counts["available"] += 1
                mosaic[(ty-ty0)*TILE_SIZE:(ty-ty0+1)*TILE_SIZE,
                       (tx-tx0)*TILE_SIZE:(tx-tx0+1)*TILE_SIZE] = arr
            else:
                counts["missing_404"] += 1
    left = -WEBMERCATOR_LIMIT + tx0 * tile_span
    right = -WEBMERCATOR_LIMIT + (tx1 + 1) * tile_span
    top = WEBMERCATOR_LIMIT - ty0 * tile_span
    bottom = WEBMERCATOR_LIMIT - (ty1 + 1) * tile_span
    return mosaic, (left, right, bottom, top), counts


def _line_geometries(raw: dict):
    geom = shape(raw)
    if geom.geom_type == "LineString":
        yield geom
    elif geom.geom_type == "MultiLineString":
        yield from geom.geoms
    elif geom.geom_type == "GeometryCollection":
        for part in geom.geoms:
            yield from _line_geometries(json.dumps(__import__("shapely.geometry", fromlist=["mapping"]).mapping(part)))


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("LOAD spatial")
    con.execute("SET geometry_always_xy=true")
    con.execute(f"CREATE VIEW wards_src AS SELECT name, geometry FROM '{ADMIN}' WHERE pref_code='13' AND city LIKE '%区'")
    con.execute("""CREATE TEMP TABLE wards AS SELECT name,
        ST_Transform(geometry::GEOMETRY, 'EPSG:4612', 'EPSG:3857', always_xy:=true) AS geom
        FROM wards_src""")
    n_wards = con.execute("SELECT count(*) FROM wards").fetchone()[0]
    if n_wards != 23:
        raise RuntimeError(f"expected 23 Tokyo wards, found {n_wards}")
    wards = con.execute("SELECT name, ST_AsGeoJSON(geom) FROM wards ORDER BY name").fetchall()
    ward_geoms = [(name, shape(_geojson(geom))) for name, geom in wards]
    ward_union = unary_union([geom for _, geom in ward_geoms])
    xmin = min(geom.bounds[0] for _, geom in ward_geoms)
    ymin = min(geom.bounds[1] for _, geom in ward_geoms)
    xmax = max(geom.bounds[2] for _, geom in ward_geoms)
    ymax = max(geom.bounds[3] for _, geom in ward_geoms)
    padding = 650.0
    map_bounds = (xmin-padding, ymin-padding, xmax+padding, ymax+padding)
    con.execute("CREATE TEMP TABLE study AS SELECT ST_Union_Agg(geom) geom FROM wards")

    transformers = {
        "OGC:CRS84": Transformer.from_crs("OGC:CRS84", "EPSG:3857", always_xy=True),
        "EPSG:4326": Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True),
    }

    point_specs = [
        ("underpass", UNDERPASS, "OGC:CRS84", "国交省アンダーパス", "#0072B2", "o"),
        ("kansui", KANSUI, "EPSG:4326", "地方整備局・冠水想定箇所", "#D55E00", "^"),
    ]
    points = {}
    counts = {}
    for key, url, source_crs, *_ in point_specs:
        rows = con.execute(f"""SELECT p.lon,p.lat FROM '{url}' p JOIN wards w
             ON ST_Within(ST_Transform(p.geometry::GEOMETRY,'{source_crs}','EPSG:4612',always_xy:=true),
                          ST_Transform(w.geom,'EPSG:3857','EPSG:4612',always_xy:=true))""").fetchall()
        trans = transformers[source_crs]
        points[key] = np.asarray([trans.transform(lon, lat) for lon, lat in rows], dtype=float).reshape((-1, 2))
        counts[key] = len(rows)

    # Historical Tokyo flood records: show recorded flood-point locations, not road-flood events.
    history_rows = con.execute(f"""SELECT ST_X(p.geometry::GEOMETRY),ST_Y(p.geometry::GEOMETRY)
        FROM '{FLOOD_RECORDS}' p JOIN wards w
        ON ST_Within(ST_Transform(p.geometry::GEOMETRY,'EPSG:4612','EPSG:4612'),
                     ST_Transform(w.geom,'EPSG:3857','EPSG:4612',always_xy:=true))""").fetchall()
    hist_transform = Transformer.from_crs("EPSG:4612", "EPSG:3857", always_xy=True)
    historical = np.asarray([hist_transform.transform(lon, lat) for lon, lat in history_rows], dtype=float).reshape((-1, 2))
    counts["tokyo_flood_record_points"] = len(history_rows)

    # Major OSM roads only; full residential streets would obscure the thematic layers at this scale.
    bx0, by0, bx1, by1 = map_bounds
    road_rows = con.execute(f"""SELECT highway, ST_AsGeoJSON(way) FROM '{OSM}'
        WHERE highway IN ('motorway','motorway_link','trunk','trunk_link','primary','primary_link',
                          'secondary','secondary_link','tertiary','tertiary_link')
          AND bbox.xmax >= {bx0} AND bbox.xmin <= {bx1}
          AND bbox.ymax >= {by0} AND bbox.ymin <= {by1}""").fetchall()
    roads = defaultdict(list)
    for highway, geometry in road_rows:
        for line in _line_geometries(_geojson(geometry)):
            clipped = line.intersection(ward_union)
            roads[highway].extend(_line_geometries(mapping(clipped)))
    counts["osm_major_road_rows_in_bbox"] = len(road_rows)
    counts["osm_clipped_road_segments"] = sum(len(v) for v in roads.values())

    # Rasterize A31a at 25 m for display. At each pixel, overlapping river
    # polygons use the largest (deepest) published rank. This is a display
    # aggregation, not a new depth model.
    flood_resolution = 25.0
    flood_width = int(math.ceil((bx1-bx0)/flood_resolution))
    flood_height = int(math.ceil((by1-by0)/flood_resolution))
    flood_transform = from_origin(bx0, by1, flood_resolution, flood_resolution)
    flood_grid = np.zeros((flood_height, flood_width), dtype=np.uint8)
    ward_mask = rasterize([(geom, 1) for _, geom in ward_geoms], out_shape=flood_grid.shape,
                          transform=flood_transform, fill=0, all_touched=True, dtype=np.uint8)
    to_geo = Transformer.from_crs("EPSG:3857", "EPSG:6668", always_xy=True)
    ll_corners = [to_geo.transform(x,y) for x,y in ((bx0,by0),(bx0,by1),(bx1,by0),(bx1,by1))]
    lon0, lon1 = min(p[0] for p in ll_corners), max(p[0] for p in ll_corners)
    lat0, lat1 = min(p[1] for p in ll_corners), max(p[1] for p in ll_corners)
    a31a_cache = ART / "a31a_maximum_25m.npy"
    a31a_meta_cache = ART / "a31a_maximum_25m.json"
    cache_meta = json.loads(a31a_meta_cache.read_text()) if a31a_meta_cache.exists() else {}
    if (a31a_cache.exists() and cache_meta.get("map_bounds") == list(map_bounds)
            and cache_meta.get("resolution_m") == flood_resolution):
        flood_grid = np.load(a31a_cache)
        a31a_counts = {int(k):v for k,v in cache_meta["feature_counts"].items()}
        a31a_rows_count = sum(a31a_counts.values())
    else:
        a31a_query = con.execute(f"""SELECT class_code, ST_AsGeoJSON(ST_Transform(geometry::GEOMETRY,
            'EPSG:6668','EPSG:3857',always_xy:=true)) FROM '{A31A}'
            WHERE category='maximum' AND ST_Intersects(ST_Envelope(geometry::GEOMETRY),
              ST_SetCRS(ST_MakeEnvelope({lon0},{lat0},{lon1},{lat1}), 'EPSG:6668'))""")
        a31a_counts = defaultdict(int)
        a31a_rows_count = 0
        while True:
            rows = a31a_query.fetchmany(1500)
            if not rows:
                break
            shapes_by_rank = defaultdict(list)
            for class_code, raw in rows:
                rank = int(class_code)
                a31a_counts[rank] += 1
                a31a_rows_count += 1
                geom = shape(_geojson(raw))
                for polygon in _polygons(geom):
                    shapes_by_rank[rank].append((polygon, 1))
            for rank, raster_shapes in shapes_by_rank.items():
                burned = rasterize(raster_shapes, out_shape=flood_grid.shape, transform=flood_transform,
                                   fill=0, all_touched=True, dtype=np.uint8)
                flood_grid[burned == 1] = np.maximum(flood_grid[burned == 1], rank)
        flood_grid[ward_mask == 0] = 0
        np.save(a31a_cache, flood_grid)
        a31a_meta_cache.write_text(json.dumps({"map_bounds":list(map_bounds),"resolution_m":flood_resolution,
                                               "feature_counts":dict(a31a_counts)},indent=2)+"\n")
    counts["a31a_maximum_polygons_in_extent"] = a31a_rows_count

    dem, dem_extent, tile_counts = _dem_mosaic(map_bounds)

    from cjk_font import use_cjk_font
    all_labels = "東京23区 アンダーパス 冠水想定 洪水浸水想定区域 OSM 標高 過去の浸水実績 2026"
    font = use_cjk_font(all_labels)
    fig, ax = plt.subplots(figsize=(14, 12), constrained_layout=True)
    ax.set_facecolor("#eaf1f5")
    masked = np.ma.masked_invalid(dem)
    finite = dem[np.isfinite(dem)]
    if finite.size:
        lo, hi = np.nanpercentile(finite, [2, 98])
        dem_cmap = "Greys_r"
        ax.imshow(masked, extent=dem_extent, origin="upper", cmap=dem_cmap, vmin=lo, vmax=hi,
                  alpha=0.50, interpolation="bilinear", zorder=0)
    else:
        dem_cmap, lo, hi = "Greys_r", 0.0, 1.0

    flood_cmap = ListedColormap(["#ffffff00", *[DEPTH_COLORS[k] for k in range(1,7)]])
    flood_norm = BoundaryNorm(np.arange(-0.5,7.5,1), flood_cmap.N)
    flood_masked = np.ma.masked_where(flood_grid == 0, flood_grid)
    ax.imshow(flood_masked, extent=(bx0,bx1,by0,by1), origin="upper", cmap=flood_cmap,
              norm=flood_norm, alpha=0.72, interpolation="nearest", zorder=2)

    road_style = {
        "motorway": ("#333333", 0.36), "motorway_link": ("#555555", 0.24),
        "trunk": ("#444444", 0.32), "trunk_link": ("#666666", 0.22),
        "primary": ("#555555", 0.27), "primary_link": ("#777777", 0.18),
        "secondary": ("#777777", 0.19), "secondary_link": ("#888888", 0.14),
        "tertiary": ("#999999", 0.13), "tertiary_link": ("#aaaaaa", 0.10),
    }
    for highway, geometries in roads.items():
        color, linewidth = road_style[highway]
        for line in geometries:
            x, y = line.xy
            ax.plot(x, y, color=color, linewidth=linewidth, alpha=0.72, zorder=3)

    for name, geom in ward_geoms:
        for polygon in _polygons(geom):
            x, y = polygon.exterior.xy
            ax.plot(x, y, color="#3d464c", linewidth=0.6, zorder=4)
        rp = geom.representative_point()
        ax.text(rp.x, rp.y, name, fontsize=7.3, ha="center", va="center", color="#263238",
                bbox={"facecolor":"white","edgecolor":"none","alpha":0.68,"pad":0.6}, zorder=5)

    # Existing flood record points are stars; these are not road-flood observations.
    if len(historical):
        ax.scatter(historical[:,0], historical[:,1], s=34, marker="*", c="#CC3311", edgecolors="white",
                   linewidths=0.35, alpha=0.95, zorder=7)
    for key, _, _, _, color, marker in point_specs:
        xy = points[key]
        if len(xy):
            if key == "underpass":
                ax.scatter(xy[:,0], xy[:,1], s=23, marker=marker, facecolors="none", edgecolors=color,
                           linewidths=0.9, alpha=0.95, zorder=8)
            else:
                ax.scatter(xy[:,0], xy[:,1], s=28, marker=marker, c=color, edgecolors="white",
                           linewidths=0.35, alpha=0.9, zorder=9)

    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    ax.set_title("東京23区｜アンダーパス・冠水想定・洪水想定・地形", fontsize=15, pad=14)
    subtitle = ("A31a: 想定最大規模（河川別ランクを重ね、重複部は最大ランク）  |  "
                "DEM10B 約10 m  |  OSM主要道路（2026-08）")
    ax.text(0.5, 1.005, subtitle, transform=ax.transAxes, ha="center", va="bottom", fontsize=9)

    handles = [
        Line2D([], [], color="#666666", lw=1.1, label="OSM主要道路"),
        Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor="#0072B2", linestyle="none",
               markersize=7, label=f"国交省アンダーパス ({counts['underpass']})"),
        Line2D([], [], marker="^", markerfacecolor="#D55E00", markeredgecolor="white", linestyle="none",
               markersize=7, label=f"地方整備局・冠水想定 ({counts['kansui']})"),
        Line2D([], [], marker="*", markerfacecolor="#CC3311", markeredgecolor="white", linestyle="none",
               markersize=9, label=f"東京都の浸水実績図・地点 ({counts['tokyo_flood_record_points']})"),
    ]
    for rank in range(1,7):
        if not a31a_counts.get(rank):
            continue
        handles.append(Patch(facecolor=DEPTH_COLORS[rank], edgecolor="none",
                             label=f"A31a {depth_label(rank)}"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.005, 0.5), frameon=True,
              framealpha=0.96, fontsize=9, title="表示レイヤー")
    from matplotlib.cm import ScalarMappable
    dem_colorbar = fig.colorbar(ScalarMappable(norm=Normalize(lo,hi),cmap=dem_cmap), ax=ax,
                                fraction=0.035, pad=0.018, shrink=0.38)
    dem_colorbar.set_label("GSI DEM10B 標高 (m)", fontsize=8)
    dem_colorbar.ax.tick_params(labelsize=7)

    # Ground-distance scale bar, correcting Web Mercator's local scale at Tokyo latitude.
    mean_lat = 35.68
    ground_scale = math.cos(math.radians(mean_lat))
    bar_ground_m = 5000
    bar_map_m = bar_ground_m / ground_scale
    sx = bx0 + (bx1-bx0)*0.045
    sy = by0 + (by1-by0)*0.09
    ax.plot([sx, sx+bar_map_m], [sy, sy], color="#111111", lw=3, solid_capstyle="butt", zorder=11)
    ax.text(sx+bar_map_m/2, sy+(by1-by0)*0.012, "地上距離 5 km", fontsize=8, ha="center", va="bottom",
            color="#111111", bbox={"facecolor":"white","edgecolor":"none","alpha":0.8,"pad":1}, zorder=11)
    ax.annotate("北", xy=(0.96,0.90), xytext=(0.96,0.82), xycoords="axes fraction", textcoords="axes fraction",
                arrowprops={"arrowstyle":"-|>","color":"#222222","lw":1.4}, ha="center", va="bottom", fontsize=9)
    fig.text(0.015, 0.012,
             "注意: A31aは河川洪水の想定で、内水・高潮等は含まない。東京都の実績点は道路冠水の記録ではない。"
             " DEMは路面標高を保証せず、OSMは2026-08時点。重なりは危険度の実証ではない。",
             fontsize=8, color="#333333")

    png = OUT / "tokyo23_underpass_a31a_osm_dem.png"
    fig.savefig(png, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    meta = {
        "question": "東京23区で、2種類の登録地点は地形・主要道路・河川洪水浸水想定・東京都の浸水実績図とどう重なるか",
        "purpose": "探索的な重ね合わせ。危険度の推定・検証ではない",
        "crs_display": "EPSG:3857 (display only; no distance/area estimates from this CRS)",
        "boundary": {"dataset":"jp-admin-2026-09", "revision":"e6c87b1d7095c17422147962185071a986e13135", "crs_source":"EPSG:4612", "wards":n_wards},
        "sources": {
            "underpass": {"revision":"4d00072aa88696cfa7026c4cef7d600bc96f9f13", "crs":"OGC:CRS84", "map_date":"2025-03-31"},
            "kansui_points": {"revision":"d4e2e1f6a3278a9956044094acd852a73c5283f2", "crs":"EPSG:4326", "snapshot":"2026-10-30", "meaning":"指定された冠水想定箇所。実績ではない"},
            "A31a": {"revision":"5b2259273128d0b79b491eb758abe0db67c4feac", "crs":"EPSG:6668", "category":"maximum", "rank_rule":"河川別ランクの重複部では最大class_codeを採用", "shown_unit":"想定最大規模の河川洪水。内水・高潮は含まない"},
            "OSM": {"revision":"38f7a5f961b6e33343d82a11152e768c37d22664", "snapshot":"2026-08-31", "crs":"EPSG:3857", "shown":"motorway–tertiary roads and links"},
            "GSI_DEM": {"layer":"dem", "zoom":DEM_Z, "nominal_ground_resolution":"about 10 m", "retrieved_utc":datetime.now(timezone.utc).isoformat(), "tiles":tile_counts},
            "tokyo_flood_record": {"revision":"354b0d9f8030347192eaa387500f60da76c07e1a", "crs":"EPSG:4612", "period":"1974–2019", "shown":"flood_point records; not road-flood observations"},
        },
        "counts_within_23_wards": {k:counts[k] for k in ("underpass","kansui","tokyo_flood_record_points")},
        "a31a_maximum_polygons_in_bbox": a31a_rows_count,
        "a31a_maximum_rank_feature_counts_in_bbox": {str(k):v for k,v in sorted(a31a_counts.items())},
        "a31a_display": {"resolution_m":flood_resolution,"aggregation":"per-pixel maximum class_code across river polygons",
                          "pixels_by_maximum_depth_rank":{str(k):int((flood_grid==k).sum()) for k in range(1,7)}},
        "osm_lines": {"candidate_rows_in_bbox":len(road_rows),"clipped_line_parts_within_wards":sum(len(v) for v in roads.values()),
                      "clipped_line_parts_by_highway":{k:len(v) for k,v in sorted(roads.items())}},
        "dem_finite_pixel_count": int(np.isfinite(dem).sum()),
        "font":font,
        "warnings": ["A31a polygons are scenario-based river flood extents; no local depth model was fitted.",
                     "GSI DEM does not establish the road-surface elevation at a covered underpass.",
                     "Tokyo flood records are not necessarily road-flood incidents."],
    }
    (OUT / "tokyo23_underpass_a31a_osm_dem.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"png":str(png),"counts":counts,"a31a_rows":a31a_rows_count,
                      "roads":len(road_rows),"dem_tiles":tile_counts},ensure_ascii=False))


if __name__ == "__main__":
    main()

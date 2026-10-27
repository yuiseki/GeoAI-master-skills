"""Draw a named categorical map or zero-centred score map from GeoJSON results.

Usage: python spatial_result_map.py results.geojson config.json map.png
The input features carry a numeric property named by config["value"]. Config also
contains question, kind, crs, source, data_version, unit and, for categories,
categories: {"0": "name", ...}. A diverging map names its negative and positive ends.

Optional geographic context in config:
- expect_units: int (stops if feature count differs)
- outline: GeoJSON Polygon/MultiPolygon for the outer study-area boundary
- context_areas: list of {"name": str, "geometry": GeoJSON} (or FeatureCollection)
  drawn as land under units, boundary lines over units, and area labels
- roads: list of {"geometry": GeoJSON LineString/MultiLineString, "tier": "major"|"minor"}
  (or FeatureCollection) drawn over units for street-level orientation
- focus_areas: list of {"name": str, "geometry": GeoJSON, "color": str} outlined and
  listed in the legend
- highlights: list of {"id": str, "label": str, "rank": str, "color": str} outlining
  specific units by properties["id"] (stops if any id is missing)
- landmarks: list of {"name": str, "coordinates": [x, y]} or {"name": str, "geometry": GeoJSON}
  placed with collision avoidance
- label_property: property name on input features to label units
- scalebar: bool (default True for known geographic or metric CRS)
"""

import argparse
import itertools
import json
import math
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from cjk_font import use_cjk_font
from matplotlib import patheffects
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch, Rectangle
from matplotlib.path import Path as MplPath

COLORS = ("#E69F00", "#4E79A7", "#9B59B6", "#009E73", "#D55E00", "#56B4E9")
NODATA = "#D9D9D9"
EDGE = "#444444"
LAND = "#EFECE6"
WATER = "#DBE9F2"
CONTEXT_LINE = "#4D4D4D"
HIGHLIGHT_COLORS = ("#8E2675", "#157F9B", "#B45F06", "#111111")
GEOGRAPHIC_CRS = {
    "EPSG:4326",
    "OGC:CRS84",
    "CRS84",
    "EPSG:4612",
    "EPSG:6668",
    "EPSG:4019",
    "EPSG:4269",
    "EPSG:4258",
}
METRIC_CRS = {
    *(f"EPSG:{code}" for code in range(6669, 6688)),
    *(f"EPSG:{code}" for code in range(32601, 32661)),
    "EPSG:3857",
}


def _signed_area(points):
    return (
        sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in itertools.pairwise(points)) / 2
    )


def _ring_path(rings):
    vertices = []
    codes = []
    for index, ring in enumerate(rings):
        points = [tuple(point[:2]) for point in ring]
        if len(points) < 4 or points[0] != points[-1]:
            raise ValueError("polygon rings must be closed")
        desired_positive = index == 0
        if (_signed_area(points) > 0) != desired_positive:
            points = list(reversed(points))
        vertices.extend(points)
        codes.extend(
            [MplPath.MOVETO, *([MplPath.LINETO] * (len(points) - 2)), MplPath.CLOSEPOLY]
        )
    return MplPath(np.asarray(vertices, dtype=float), codes)


def _polygons(feature):
    geometry = feature.get("geometry", feature) or {}
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Polygon":
        return [coordinates]
    if kind == "MultiPolygon":
        return coordinates
    raise ValueError(f"polygon geometry required, got {kind}")


def _lines(feature):
    geometry = feature.get("geometry", feature) or {}
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "LineString":
        return [coordinates]
    if kind == "MultiLineString":
        return coordinates
    raise ValueError(f"line geometry required, got {kind}")


def _ring_abs_area(ring):
    return abs(_signed_area([tuple(p[:2]) for p in ring]))


def _interior_point(polygons):
    """Find a point strictly inside the largest polygon part using horizontal scanlines."""
    best_poly = max(polygons, key=lambda poly: _ring_abs_area(poly[0]))
    ext = [tuple(p[:2]) for p in best_poly[0]]
    ys = [p[1] for p in ext]
    ymin, ymax = min(ys), max(ys)
    if ymin == ymax:
        xs = [p[0] for p in ext]
        return (min(xs) + max(xs)) / 2, ymin
    best_seg = None
    for frac in (0.5, 0.45, 0.55, 0.38, 0.62, 0.3, 0.7):
        y = ymin + frac * (ymax - ymin)
        xs = []
        for (x1, y1), (x2, y2) in itertools.pairwise(ext):
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for x_left, x_right in zip(xs[0::2], xs[1::2]):
            width = x_right - x_left
            score = width * (1.0 - abs(frac - 0.5))
            if best_seg is None or score > best_seg[0]:
                best_seg = (score, (x_left + x_right) / 2, y)
    if best_seg is not None:
        return best_seg[1], best_seg[2]
    xs = [p[0] for p in ext]
    return (min(xs) + max(xs)) / 2, (ymin + ymax) / 2


def _point_coords(item):
    if "coordinates" in item and isinstance(item["coordinates"], (list, tuple)):
        coords = item["coordinates"]
        if len(coords) >= 2 and isinstance(coords[0], (int, float)):
            return float(coords[0]), float(coords[1])
    if "lon" in item and "lat" in item:
        return float(item["lon"]), float(item["lat"])
    if "x" in item and "y" in item:
        return float(item["x"]), float(item["y"])
    geom = item.get("geometry", item)
    if geom.get("type") == "Point":
        c = geom["coordinates"]
        return float(c[0]), float(c[1])
    return _interior_point(_polygons(geom))


def _normalize_areas(raw):
    if not raw:
        return []
    if isinstance(raw, dict) and raw.get("type") == "FeatureCollection":
        items = raw.get("features", [])
    else:
        items = raw
    out = []
    for item in items:
        props = item.get("properties") or {}
        name = item.get("name", props.get("name", ""))
        geom = item.get("geometry", item)
        out.append({"name": "" if name is None else str(name), "geometry": geom})
    return out


def _normalize_roads(raw):
    if not raw:
        return []
    if isinstance(raw, dict) and raw.get("type") == "FeatureCollection":
        items = raw.get("features", [])
    else:
        items = raw
    out = []
    for item in items:
        props = item.get("properties") or {}
        tier = item.get("tier", props.get("tier", "major"))
        geom = item.get("geometry", item)
        out.append({"tier": str(tier), "geometry": geom})
    return out


def _meters_per_x_unit(crs: str, mid_lat: float) -> float | None:
    upper = crs.upper()
    if upper in GEOGRAPHIC_CRS:
        return 111_320.0 * math.cos(math.radians(mid_lat))
    if upper in METRIC_CRS:
        return 1.0
    return None


def _choose_scalebar(width_m: float) -> tuple[float, str]:
    target = width_m * 0.16
    candidates = (
        (50, "50 m"),
        (100, "100 m"),
        (200, "200 m"),
        (500, "500 m"),
        (1000, "1 km"),
        (2000, "2 km"),
        (5000, "5 km"),
        (10000, "10 km"),
        (20000, "20 km"),
        (50000, "50 km"),
        (100000, "100 km"),
    )
    best = min(candidates, key=lambda c: abs(math.log(max(target, 1.0) / c[0])))
    return float(best[0]), best[1]


def _draw_scalebar_and_north(ax, view, crs: str):
    xmin, xmax, ymin, ymax = view
    m_per_unit = _meters_per_x_unit(crs, (ymin + ymax) / 2)
    if m_per_unit is None or m_per_unit <= 0:
        return None, []
    width_m = (xmax - xmin) * m_per_unit
    length_m, label = _choose_scalebar(width_m)
    bar_dx = length_m / m_per_unit
    dx = xmax - xmin
    dy = ymax - ymin
    x0 = xmin + 0.04 * dx
    y0 = ymin + 0.035 * dy
    bar_h = 0.006 * dy
    halo = [patheffects.withStroke(linewidth=2.5, foreground="white")]
    ax.add_patch(
        Rectangle(
            (x0 - 0.01 * dx, y0 - 0.012 * dy),
            bar_dx + 0.02 * dx,
            0.052 * dy,
            facecolor="white",
            edgecolor="none",
            alpha=0.78,
            zorder=8,
        )
    )
    ax.add_patch(
        Rectangle((x0, y0), bar_dx, bar_h, facecolor="#111111", edgecolor="#111111", zorder=9)
    )
    t_scale = ax.text(
        x0 + bar_dx / 2,
        y0 + 0.012 * dy,
        label,
        ha="center",
        va="bottom",
        fontsize=8,
        color="#111111",
        path_effects=halo,
        zorder=9,
    )
    t_north = ax.text(
        xmax - 0.035 * dx,
        ymax - 0.04 * dy,
        "北↑",
        ha="right",
        va="top",
        fontsize=9,
        color="#111111",
        weight="bold",
        bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.8},
        zorder=9,
    )
    return int(length_m), [t_scale, t_north]


def _place_labels_without_overlap(fig, ax, candidates, view, existing_texts):
    """Place candidate labels trying small offsets so their bounding boxes do not overlap."""
    xmin, xmax, ymin, ymax = view
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    placed_boxes = [
        t.get_window_extent(renderer).expanded(1.06, 1.12)
        for t in existing_texts
        if t.get_visible() and t.get_text()
    ]
    placed_texts = []
    offsets = (
        (0, 0),
        (0, 9),
        (0, -9),
        (14, 0),
        (-14, 0),
        (11, 8),
        (-11, 8),
        (11, -8),
        (-11, -8),
        (0, 16),
        (0, -16),
    )
    for item in candidates:
        x, y = item["x"], item["y"]
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            continue
        text_str = item["text"]
        fontsize = item.get("fontsize", 8)
        color = item.get("color", "#1f1f1f")
        weight = item.get("weight", "normal")
        bbox_style = item.get(
            "bbox",
            {"boxstyle": "round,pad=0.14", "fc": "white", "ec": "none", "alpha": 0.78},
        )
        zorder = item.get("zorder", 7)
        chosen = None
        for ox, oy in offsets:
            artist = ax.annotate(
                text_str,
                (x, y),
                xytext=(ox, oy),
                textcoords="offset points",
                ha="center",
                va="center",
                fontsize=fontsize,
                color=color,
                weight=weight,
                bbox=bbox_style,
                zorder=zorder,
                annotation_clip=True,
            )
            fig.canvas.draw()
            ext = artist.get_window_extent(renderer)
            if not any(ext.overlaps(b) for b in placed_boxes):
                chosen = artist
                placed_boxes.append(ext.expanded(1.06, 1.12))
                break
            artist.remove()
        if chosen is not None:
            placed_texts.append(chosen)
    return placed_texts


def _measure_text_overlaps(fig, texts, legends=()):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [
        (t.get_text(), t.get_window_extent(renderer))
        for t in texts
        if t.get_visible() and t.get_text()
    ]
    found = []
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1 :]:
            if ba.overlaps(bb):
                found.append([a, b])
        for leg in legends:
            if leg is not None and ba.overlaps(leg.get_window_extent(renderer)):
                found.append([a, "legend"])
    return found


def _fmt_break(val: float) -> str:
    return f"{val:,.0f}" if abs(val) >= 1000 else f"{val:.4g}"


def _compute_breaks(
    finite: list[float],
    method: str,
    n_classes: int,
    thresholds: list[float] | None = None,
) -> list[float]:
    arr = np.asarray(finite, dtype=float)
    lo, hi = float(arr.min()), float(arr.max())
    if method == "equal":
        return list(np.linspace(lo, hi, n_classes + 1))
    if method == "quantile":
        return list(np.quantile(arr, np.linspace(0, 1, n_classes + 1)))
    if method == "fixed":
        if not thresholds:
            raise ValueError("thresholds required for fixed class_method")
        t = sorted(float(v) for v in thresholds)
        return [lo, *t, hi]
    raise ValueError(f"unknown class_method: {method}")


def _assign_classes(finite: list[float], breaks: list[float]) -> np.ndarray:
    return np.searchsorted(
        np.asarray(breaks[1:-1], dtype=float),
        np.asarray(finite, dtype=float),
        side="left",
    )


def draw(input_path: Path, config_path: Path, output: Path):
    data = json.loads(input_path.read_text())
    config = json.loads(config_path.read_text())
    features = data.get("features", [])
    if not features or data.get("type") != "FeatureCollection":
        raise ValueError("nonempty GeoJSON FeatureCollection required")
    expect_units = config.get("expect_units")
    if expect_units is not None and len(features) != int(expect_units):
        raise ValueError(f"expected {expect_units} units, got {len(features)}")
    kind = config["kind"]
    if kind not in ("category", "diverging", "sequential"):
        raise ValueError("kind must be category, diverging, or sequential")
    value_key = config["value"]
    values = [feature["properties"].get(value_key) for feature in features]
    finite = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not finite:
        raise ValueError("no finite values")
    nodata = len(values) - len(finite)

    breaks = None
    class_changes = None
    if kind == "category":
        categories = config["categories"]
        keys = sorted({str(int(v)) for v in finite}, key=int)
        if any(float(v) != int(v) for v in finite):
            raise ValueError("category values must be integers")
        unknown = set(keys) - categories.keys()
        if unknown:
            raise ValueError(f"unlabelled category: {', '.join(sorted(unknown))}")
        if len(keys) > len(COLORS):
            raise ValueError(f"palette supports at most {len(COLORS)} categories")
        if len({categories[key] for key in keys}) != len(keys):
            raise ValueError("category names must be distinct")
        counts = {
            categories[key]: sum(int(v) == int(key) for v in finite) for key in keys
        }
        custom_colors = config.get("category_colors") or {}
        color_by_key = {
            key: custom_colors.get(key, COLORS[i % len(COLORS)])
            for i, key in enumerate(keys)
        }
        labels = [
            f"{categories[key]}  {counts[categories[key]]} {config['unit']}"
            for key in keys
        ]
    elif kind == "sequential":
        cls_method = config.get("class_method", "quantile")
        n_classes = int(config.get("classes", 5))
        palette_name = config.get("palette", "YlOrRd")
        value_unit = config.get("value_unit", "")
        breaks = _compute_breaks(
            finite, cls_method, n_classes, config.get("thresholds")
        )
        cls_idx = _assign_classes(finite, breaks)
        cls_counts = np.bincount(cls_idx, minlength=n_classes).tolist()
        cmap_seq = plt.get_cmap(palette_name, n_classes)
        keys = [str(i) for i in range(n_classes)]
        color_by_key = {str(i): cmap_seq(i) for i in range(n_classes)}
        unit_suffix = f" {value_unit}" if value_unit else ""
        labels = [
            f"{_fmt_break(breaks[i])}〜{_fmt_break(breaks[i + 1])}{unit_suffix}  ({cls_counts[i]} {config['unit']})"
            for i in range(n_classes)
        ]
        counts = {labels[i]: cls_counts[i] for i in range(n_classes)}
        compare_methods = config.get("compare_methods") or []
        if compare_methods:
            class_changes = {}
            for cm in compare_methods:
                other_b = _compute_breaks(
                    finite, cm, n_classes, config.get("thresholds")
                )
                other_cls = _assign_classes(finite, other_b)
                class_changes[cm] = round(float(np.mean(cls_idx != other_cls)), 3)
    else:
        span = max(abs(v) for v in finite) or 1.0
        norm = TwoSlopeNorm(vmin=-span, vcenter=0, vmax=span)
        cmap = plt.get_cmap("RdBu_r")
        counts = None
        labels = [config["negative"], config["positive"]]

    context_areas = _normalize_areas(config.get("context_areas"))
    roads = _normalize_roads(config.get("roads"))
    focus_areas = config.get("focus_areas") or []
    highlights = config.get("highlights") or []
    point_groups = config.get("point_groups") or []
    landmarks = list(config.get("landmarks") or [])
    label_prop = config.get("label_property")
    if label_prop:
        for feature in features:
            nm = feature.get("properties", {}).get(label_prop)
            if nm:
                landmarks.append({"name": str(nm), "geometry": feature["geometry"]})

    by_id = {
        str(feature.get("properties", {}).get("id", idx)): feature
        for idx, feature in enumerate(features)
    }
    for hl in highlights:
        hid = str(hl["id"])
        if hid not in by_id:
            raise ValueError(f"highlighted id not found in features: {hid}")

    extra_strings = [
        *(a["name"] for a in context_areas if a.get("name")),
        *(f.get("name", "") for f in focus_areas),
        *(h.get("label", "") for h in highlights),
        *(h.get("rank", "") for h in highlights),
        *(pg.get("label", "") for pg in point_groups),
        *(lm.get("name", "") for lm in landmarks),
        "北↑ 50 100 200 500 m 1 2 5 10 20 50 100 km",
    ]
    footer = (
        f"n={len(features)} {config['unit']} / NoData={nodata} / "
        f"{config['crs']} / {config['data_version']}"
    )
    font = use_cjk_font(
        " ".join(
            [
                config["question"],
                footer,
                *labels,
                config["source"],
                "← 0 →",
                *extra_strings,
            ]
        )
    )
    fig, ax = plt.subplots(figsize=(11.0, 8.0))
    if context_areas or config.get("water_background"):
        ax.set_facecolor(WATER)
    for area in context_areas:
        for polygon in _polygons(area["geometry"]):
            path = _ring_path(polygon[:1])
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor=LAND,
                    edgecolor="none",
                    zorder=0,
                )
            )

    all_points = []
    unit_lw = float(config.get("unit_linewidth", 0.38))
    for feature, value in zip(features, values, strict=True):
        missing = value is None or not math.isfinite(float(value))
        if missing:
            face = NODATA
        elif kind == "category":
            face = color_by_key[str(int(value))]
        elif kind == "sequential":
            c_idx = int(_assign_classes([float(value)], breaks)[0])
            face = color_by_key[str(c_idx)]
        else:
            face = cmap(norm(float(value)))
        for polygon in _polygons(feature):
            path = _ring_path(polygon)
            all_points.extend(path.vertices)
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor=face,
                    edgecolor=EDGE,
                    linewidth=unit_lw,
                    hatch="//" if missing else None,
                    zorder=2,
                )
            )

    for road in roads:
        is_major = road.get("tier", "major") == "major"
        color = "#686868" if is_major else "#B0B0B0"
        lw = 0.85 if is_major else 0.35
        alpha = 0.65 if is_major else 0.45
        zorder = 3.2 if is_major else 2.6
        for coords in _lines(road["geometry"]):
            pts = np.asarray([p[:2] for p in coords], dtype=float)
            if len(pts) >= 2:
                ax.plot(
                    pts[:, 0],
                    pts[:, 1],
                    color=color,
                    linewidth=lw,
                    alpha=alpha,
                    solid_capstyle="round",
                    zorder=zorder,
                )

    for area in context_areas:
        for polygon in _polygons(area["geometry"]):
            path = _ring_path(polygon[:1])
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor="none",
                    edgecolor=CONTEXT_LINE,
                    linewidth=float(config.get("context_linewidth", 0.65)),
                    zorder=4,
                )
            )

    if config.get("outline"):
        for polygon in _polygons({"geometry": config["outline"]}):
            path = _ring_path(polygon[:1])
            all_points.extend(path.vertices)
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor="none",
                    edgecolor="#111111",
                    linewidth=1.25,
                    zorder=4.5,
                )
            )

    focus_handles = []
    for idx, focus in enumerate(focus_areas):
        fcolor = focus.get("color", HIGHLIGHT_COLORS[idx % len(HIGHLIGHT_COLORS)])
        fstyle = focus.get("linestyle", "-")
        flw = float(focus.get("linewidth", 2.0))
        for polygon in _polygons(focus["geometry"]):
            path = _ring_path(polygon[:1])
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor="none",
                    edgecolor="white",
                    linewidth=flw + 1.4,
                    zorder=4.8,
                )
            )
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor="none",
                    edgecolor=fcolor,
                    linewidth=flw,
                    linestyle=fstyle,
                    zorder=5,
                )
            )
        if focus.get("name"):
            focus_handles.append(
                Patch(
                    facecolor="none",
                    edgecolor=fcolor,
                    linewidth=flw,
                    linestyle=fstyle,
                    label=focus["name"],
                )
            )

    points = np.asarray(all_points)
    xmin, ymin = points.min(axis=0)
    xmax, ymax = points.max(axis=0)
    padx = max((xmax - xmin) * 0.04, 0.001)
    pady = max((ymax - ymin) * 0.04, 0.001)
    view = (xmin - padx, xmax + padx, ymin - pady, ymax + pady)
    ax.set_xlim(view[0], view[1])
    ax.set_ylim(view[2], view[3])
    if config["crs"].upper() in GEOGRAPHIC_CRS:
        ax.set_aspect(1 / math.cos(math.radians((ymin + ymax) / 2)))
    else:
        ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(config["question"], fontsize=15, loc="left", pad=14)

    scalebar_m = None
    fixed_texts = []
    if config.get("scalebar", True):
        scalebar_m, sb_texts = _draw_scalebar_and_north(ax, view, config["crs"])
        fixed_texts.extend(sb_texts)

    label_candidates = []
    highlight_handles = []
    for idx, hl in enumerate(highlights):
        hid = str(hl["id"])
        feat = by_id[hid]
        hcolor = hl.get("color", HIGHLIGHT_COLORS[idx % len(HIGHLIGHT_COLORS)])
        polys = _polygons(feat)
        for polygon in polys:
            path = _ring_path(polygon[:1])
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor="none",
                    edgecolor="white",
                    linewidth=3.0,
                    zorder=5.8,
                )
            )
            ax.add_patch(
                PathPatch(
                    path,
                    facecolor="none",
                    edgecolor=hcolor,
                    linewidth=1.8,
                    zorder=6,
                )
            )
        hx, hy = _interior_point(polys)
        badge = hl.get("rank") or hl.get("badge")
        if badge:
            label_candidates.append(
                {
                    "x": hx,
                    "y": hy,
                    "text": str(badge),
                    "fontsize": 8.5,
                    "color": hcolor,
                    "weight": "bold",
                    "bbox": {
                        "boxstyle": "round,pad=0.16",
                        "fc": "white",
                        "ec": hcolor,
                        "lw": 0.9,
                        "alpha": 0.92,
                    },
                    "zorder": 8.5,
                    "kind": "highlight",
                }
            )
        if hl.get("label"):
            prefix = f"{badge}. " if badge else ""
            highlight_handles.append(
                Patch(
                    facecolor="none",
                    edgecolor=hcolor,
                    linewidth=1.8,
                    label=f"{prefix}{hl['label']}",
                )
            )

    point_handles = []
    for pg in point_groups:
        pts_raw = pg.get("points") or []
        if not pts_raw:
            continue
        pcolor = pg.get("color", "#D55E00")
        pedge = pg.get("edgecolor", "#111111")
        pmarker = pg.get("marker", "o")
        psize = float(pg.get("size", 28.0))
        plw = float(pg.get("linewidth", 0.8))
        palpha = float(pg.get("alpha", 0.9))
        pzorder = float(pg.get("zorder", 6.2))
        pxs, pys = [], []
        for item in pts_raw:
            if isinstance(item, dict):
                px, py = _point_coords(item)
                badge = item.get("rank") or item.get("badge")
                if badge:
                    label_candidates.append(
                        {
                            "x": px,
                            "y": py,
                            "text": str(badge),
                            "fontsize": 8.0,
                            "color": pedge if pcolor == "none" else pcolor,
                            "weight": "bold",
                            "bbox": {
                                "boxstyle": "round,pad=0.14",
                                "fc": "white",
                                "ec": pedge if pcolor == "none" else pcolor,
                                "lw": 0.8,
                                "alpha": 0.9,
                            },
                            "zorder": 8.6,
                            "kind": "highlight",
                        }
                    )
            else:
                px, py = float(item[0]), float(item[1])
            pxs.append(px)
            pys.append(py)
        ax.scatter(
            pxs,
            pys,
            s=psize,
            c=pcolor,
            edgecolors=pedge,
            marker=pmarker,
            linewidths=plw,
            alpha=palpha,
            zorder=pzorder,
        )
        if pg.get("label"):
            point_handles.append(
                Line2D(
                    [0],
                    [0],
                    marker=pmarker,
                    linestyle="none",
                    markerfacecolor=pcolor,
                    markeredgecolor=pedge,
                    markeredgewidth=plw,
                    markersize=max(math.sqrt(psize), 5.0),
                    label=pg["label"],
                )
            )

    for lm in landmarks:
        if not lm.get("name"):
            continue
        lx, ly = _point_coords(lm)
        label_candidates.append(
            {
                "x": lx,
                "y": ly,
                "text": str(lm["name"]),
                "fontsize": float(lm.get("fontsize", config.get("landmark_fontsize", 8.0))),
                "color": lm.get("color", "#1a1a1a"),
                "weight": lm.get("weight", "normal"),
                "bbox": {
                    "boxstyle": "round,pad=0.14",
                    "fc": "white",
                    "ec": "none",
                    "alpha": 0.8,
                },
                "zorder": 7.5,
                "kind": "landmark",
            }
        )

    whole_box_area = (view[1] - view[0]) * (view[3] - view[2])
    min_share = float(config.get("context_label_min_share", 0.003))
    for area in context_areas:
        if not area.get("name"):
            continue
        polys = _polygons(area["geometry"])
        poly_area = sum(_ring_abs_area(p[0]) for p in polys)
        if poly_area < min_share * whole_box_area:
            continue
        ax_x, ax_y = _interior_point(polys)
        label_candidates.append(
            {
                "x": ax_x,
                "y": ax_y,
                "text": area["name"],
                "fontsize": float(config.get("context_fontsize", 7.8)),
                "color": "#222222",
                "weight": "normal",
                "bbox": {
                    "boxstyle": "round,pad=0.13",
                    "fc": "white",
                    "ec": "none",
                    "alpha": 0.75,
                },
                "zorder": 7.0,
                "kind": "area",
            }
        )

    legends = []
    if kind in ("category", "sequential"):
        handles = [
            Patch(facecolor=color_by_key[key], edgecolor=EDGE, label=label)
            for key, label in zip(keys, labels, strict=True)
        ]
        if nodata:
            handles.append(
                Patch(facecolor=NODATA, hatch="//", label=f"NoData  {nodata}")
            )
        if roads:
            handles.append(
                Line2D([0], [0], color="#686868", lw=1.1, label="主要道路 (OSM)")
            )
        handles.extend(focus_handles)
        handles.extend(highlight_handles)
        handles.extend(point_handles)
        leg = ax.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            frameon=False,
            fontsize=9,
        )
        legends.append(leg)
    else:
        extra_handles = []
        if nodata:
            extra_handles.append(
                Patch(facecolor=NODATA, hatch="//", label=f"NoData  {nodata}")
            )
        if roads:
            extra_handles.append(
                Line2D([0], [0], color="#686868", lw=1.1, label="主要道路 (OSM)")
            )
        extra_handles.extend(focus_handles)
        extra_handles.extend(highlight_handles)
        extra_handles.extend(point_handles)
        scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        cb_kwargs = (
            {"shrink": 0.58, "pad": 0.03, "anchor": (0.0, 0.95)}
            if extra_handles
            else {"shrink": 0.72, "pad": 0.03}
        )
        colorbar = fig.colorbar(scalar, ax=ax, **cb_kwargs)
        colorbar.set_label(f"{config['negative']}  ←  0  →  {config['positive']}")
        if extra_handles:
            leg = ax.legend(
                handles=extra_handles,
                loc="lower left",
                bbox_to_anchor=(1.03, 0.02),
                frameon=False,
                fontsize=8.5,
            )
            legends.append(leg)

    fig.text(0.02, 0.025, footer, fontsize=8, color="#444444")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    placed_texts = _place_labels_without_overlap(
        fig, ax, label_candidates, view, fixed_texts
    )
    overlaps = _measure_text_overlaps(fig, fixed_texts + placed_texts, legends)
    if config.get("stop_on_overlap") and overlaps:
        plt.close(fig)
        raise ValueError(f"overlapping texts on map: {overlaps[:5]}")

    labelled_texts = [t.get_text() for t in placed_texts]
    area_names = {a["name"] for a in context_areas if a.get("name")}
    landmark_names = {lm["name"] for lm in landmarks if lm.get("name")}
    metadata = {
        "question": config["question"],
        "kind": kind,
        "value": value_key,
        "unit": config["unit"],
        "n": len(features),
        "nodata": nodata,
        "counts": counts,
        "breaks": [round(float(x), 4) for x in breaks] if breaks is not None else None,
        "class_method": config.get("class_method", "quantile") if kind == "sequential" else None,
        "class_changes": class_changes,
        "scale": [-span, span] if kind == "diverging" else None,
        "categories": config.get("categories") if kind == "category" else None,
        "crs": config["crs"],
        "source": config["source"],
        "geometry_source": config.get("geometry_source"),
        "data_version": config["data_version"],
        "font": font,
        "source_commit": config.get("source_commit"),
        "method": config.get("method"),
        "outline": bool(config.get("outline")),
        "context_areas_count": len(context_areas),
        "labelled_areas": [t for t in labelled_texts if t in area_names],
        "roads_count": len(roads),
        "landmarks_count": len(landmarks),
        "labelled_landmarks": [t for t in labelled_texts if t in landmark_names],
        "focus_areas": [f.get("name") for f in focus_areas if f.get("name")],
        "highlights_count": len(highlights),
        "highlights": [
            {
                "id": str(h["id"]),
                "rank": h.get("rank") or h.get("badge"),
                "label": h.get("label"),
            }
            for h in highlights
        ],
        "point_groups": [
            {"label": pg.get("label"), "count": len(pg.get("points") or [])}
            for pg in point_groups
            if pg.get("points")
        ],
        "scalebar_m": scalebar_m,
        "text_overlaps": overlaps,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(
            output,
            dpi=170,
            bbox_inches="tight",
            metadata={"Description": json.dumps(metadata, ensure_ascii=False)},
        )
    plt.close(fig)
    output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(args.input, args.config, args.output)


if __name__ == "__main__":
    main()

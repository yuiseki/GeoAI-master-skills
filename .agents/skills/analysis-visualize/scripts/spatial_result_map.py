"""Draw a named categorical map or zero-centred score map from GeoJSON results.

Usage: python spatial_result_map.py results.geojson config.json map.png
The input features carry a numeric property named by config["value"]. Config also
contains question, kind, crs, source, data_version, unit and, for categories,
categories: {"0": "name", ...}. A diverging map names its negative and positive ends.
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
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as MplPath

COLORS = ("#E69F00", "#4E79A7", "#9B59B6", "#009E73", "#D55E00", "#56B4E9")
NODATA = "#D9D9D9"
EDGE = "#444444"


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
    geometry = feature.get("geometry") or {}
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Polygon":
        return [coordinates]
    if kind == "MultiPolygon":
        return coordinates
    raise ValueError(f"polygon geometry required, got {kind}")


def draw(input_path: Path, config_path: Path, output: Path):
    data = json.loads(input_path.read_text())
    config = json.loads(config_path.read_text())
    features = data.get("features", [])
    if not features or data.get("type") != "FeatureCollection":
        raise ValueError("nonempty GeoJSON FeatureCollection required")
    kind = config["kind"]
    if kind not in ("category", "diverging"):
        raise ValueError("kind must be category or diverging")
    value_key = config["value"]
    values = [feature["properties"].get(value_key) for feature in features]
    finite = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not finite:
        raise ValueError("no finite values")
    nodata = len(values) - len(finite)

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
        color_by_key = {key: COLORS[i % len(COLORS)] for i, key in enumerate(keys)}
        labels = [
            f"{categories[key]}  {counts[categories[key]]} {config['unit']}"
            for key in keys
        ]
    else:
        span = max(abs(v) for v in finite) or 1.0
        norm = TwoSlopeNorm(vmin=-span, vcenter=0, vmax=span)
        cmap = plt.get_cmap("RdBu_r")
        counts = None
        labels = [config["negative"], config["positive"]]

    footer = (
        f"n={len(features)} {config['unit']} / NoData={nodata} / "
        f"{config['crs']} / {config['data_version']}"
    )
    font = use_cjk_font(
        " ".join([config["question"], footer, *labels, config["source"], "← 0 →"])
    )
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    all_points = []
    for feature, value in zip(features, values, strict=True):
        missing = value is None or not math.isfinite(float(value))
        if missing:
            face = NODATA
        elif kind == "category":
            face = color_by_key[str(int(value))]
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
                    linewidth=0.38,
                    hatch="//" if missing else None,
                )
            )
    if config.get("outline"):
        for polygon in _polygons({"geometry": config["outline"]}):
            # Unioned administrative borders can contain zero-area interior seams.
            # The overview outline only needs the exterior of each part.
            path = _ring_path(polygon[:1])
            all_points.extend(path.vertices)
            ax.add_patch(
                PathPatch(path, facecolor="none", edgecolor="#111111", linewidth=1.2)
            )
    points = np.asarray(all_points)
    xmin, ymin = points.min(axis=0)
    xmax, ymax = points.max(axis=0)
    padx = max((xmax - xmin) * 0.035, 0.001)
    pady = max((ymax - ymin) * 0.035, 0.001)
    ax.set_xlim(xmin - padx, xmax + padx)
    ax.set_ylim(ymin - pady, ymax + pady)
    if config["crs"] in ("OGC:CRS84", "EPSG:4326"):
        ax.set_aspect(1 / math.cos(math.radians((ymin + ymax) / 2)))
    else:
        ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(config["question"], fontsize=16, loc="left", pad=16)
    if kind == "category":
        handles = [
            Patch(facecolor=color_by_key[key], edgecolor=EDGE, label=label)
            for key, label in zip(keys, labels, strict=True)
        ]
        if nodata:
            handles.append(
                Patch(facecolor=NODATA, hatch="//", label=f"NoData  {nodata}")
            )
        ax.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            frameon=False,
        )
    else:
        scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        colorbar = fig.colorbar(scalar, ax=ax, shrink=0.72, pad=0.03)
        colorbar.set_label(f"{config['negative']}  ←  0  →  {config['positive']}")
    fig.text(0.02, 0.025, footer, fontsize=8, color="#444444")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata = {
        "question": config["question"],
        "kind": kind,
        "value": value_key,
        "unit": config["unit"],
        "n": len(features),
        "nodata": nodata,
        "counts": counts,
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

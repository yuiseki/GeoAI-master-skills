"""Map the two pinned MLIT point inventories within Tokyo's 23 special wards."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb
from shapely.geometry import Polygon, mapping, shape

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "projects/_flood/underpass-ponding-exposure/outputs"
MAP_SCRIPT = ROOT / ".agents/skills/analysis-visualize/scripts/spatial_result_map.py"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
UNDERPASS = "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet"
KANSUI = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet"
MAP_CRS = "EPSG:6677"


def remove_zero_area_holes(geometry: dict) -> dict:
    """Drop zero-area boundary artifacts while retaining genuine polygon holes."""
    geom = shape(geometry)
    polygons = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    cleaned = [
        Polygon(
            polygon.exterior.coords,
            [ring.coords for ring in polygon.interiors if Polygon(ring).area > 0.01],
        )
        for polygon in polygons
    ]
    if geom.geom_type == "MultiPolygon":
        from shapely.geometry import MultiPolygon

        return mapping(MultiPolygon(cleaned))
    return mapping(cleaned[0])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("LOAD spatial")
    con.execute("SET geometry_always_xy = true")
    # Tokyo's special wards are stored in `city`; `ward` is reserved for
    # designated-city subdivisions in this dataset.
    con.execute(f"CREATE VIEW wards AS SELECT name, geometry FROM '{ADMIN}' WHERE pref_code='13' AND city LIKE '%区'")
    ward_rows = con.execute(
        f"SELECT name, ST_AsGeoJSON(ST_Transform(geometry::GEOMETRY, 'EPSG:4612', '{MAP_CRS}')) FROM wards ORDER BY name"
    ).fetchall()
    if len(ward_rows) != 23:
        raise RuntimeError(f"expected 23 Tokyo wards, got {len(ward_rows)}")

    datasets = (
        ("underpass", UNDERPASS, "OGC:CRS84", "geometry"),
        ("kansui", KANSUI, "EPSG:4326", "geometry"),
    )
    point_groups = []
    counts = {}
    with tempfile.TemporaryDirectory(prefix="tokyo23-underpass-map-") as tmp:
        geojson_path = Path(tmp) / "wards.geojson"
        features = []
        context_areas = []
        for name, geometry_json in ward_rows:
            geometry = remove_zero_area_holes(json.loads(geometry_json))
            features.append({"type": "Feature", "properties": {"name": name, "value": 0}, "geometry": geometry})
            context_areas.append({"name": name, "geometry": geometry})

        for key, url, source_crs, geom_col in datasets:
            view = f"{key}_points"
            con.execute(f"CREATE VIEW {view} AS SELECT * FROM '{url}'")
            # Use the source geometry's declared CRS for the point-in-ward test.
            matched = con.execute(
                f"""SELECT ST_X(ST_Transform(p.{geom_col}::GEOMETRY, '{source_crs}', '{MAP_CRS}')),
                           ST_Y(ST_Transform(p.{geom_col}::GEOMETRY, '{source_crs}', '{MAP_CRS}'))
                    FROM {view} p JOIN wards w
                    ON ST_Within(ST_Transform(p.{geom_col}::GEOMETRY, '{source_crs}', 'EPSG:4612'), w.geometry)"""
            ).fetchall()
            counts[key] = len(matched)
            point_coords = []
            for x, y in matched:
                point_coords.append([float(x), float(y)])
            label, color, marker = (
                ("国交省アンダーパス", "none", "o")
                if key == "underpass"
                else ("地方整備局・冠水想定箇所", "#D55E00", "^")
            )
            point_groups.append({
                "label": f"{label} ({len(point_coords)}地点)",
                "color": color,
                "edgecolor": "#0072B2" if key == "underpass" else "#FFFFFF",
                "marker": marker,
                "size": 24 if key == "underpass" else 34,
                "linewidth": 0.45,
                "alpha": 0.86,
                "zorder": 7 if key == "underpass" else 6,
                "points": point_coords,
            })

        geojson_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False))
        config = {
            "question": "東京23区で、2種類の国土交通省関連地点はどこに分布するか？",
            "value": "value",
            "kind": "category",
            "categories": {"0": "東京23区"},
            "category_colors": {"0": "#F2F0EB"},
            "unit": "区",
            "crs": MAP_CRS,
            "source": "mlit-underpass + mlit-kansui-flood-prone-points-jp-2026-09 + jp-admin-2026-09",
            "data_version": "underpass map date 2025-03-31; kansui snapshot 2026-10-30; admin boundary/population vintage 2020",
            "geometry_source": "jp-admin-2026-09 municipalities.parquet (Tokyo 23 ward polygons; transformed from EPSG:4612)",
            "expect_units": 23,
            "context_areas": context_areas,
            "context_linewidth": 0.65,
            "point_groups": point_groups,
            "scalebar": True,
        }
        config_path = Path(tmp) / "map.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False))
        png_path = OUT / "tokyo23_underpass_and_kansui_points.png"
        subprocess.run([sys.executable, str(MAP_SCRIPT), str(geojson_path), str(config_path), str(png_path)], check=True)

    metadata_path = OUT / "tokyo23_underpass_and_kansui_points.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["source_counts_within_23_wards"] = counts
    metadata["spatial_filter"] = "ST_Within(point, Tokyo 23 ward polygons); parent-city geometries excluded"
    metadata["interpretation_note"] = "kansui points are designated flood-prone locations, not observed inundation events"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"png": str(png_path), "counts": counts, "metadata": str(metadata_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

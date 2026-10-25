"""Explore fixed CTrees/ForTy estimates; never interpret model differences as true loss.

Run: uvx --with duckdb --with shapely python projects/hokkaido-forest-biomass-survey/scripts/analyze.py
"""

import csv
import json
from datetime import date
from pathlib import Path

import duckdb
from shapely import STRtree, from_wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CTREES_REV = "e0edd7cd9812847d1740cf1b35ac84885cde3bef"
FORTY_REV = "7247d816be42065330e34909dd9ffcb66d8876bb"
CTREES_URL = ("https://huggingface.co/datasets/yuiseki/ctrees-agb-hokkaido-east-100m/"
               f"resolve/{CTREES_REV}/data/parquet/ctrees_agb_hokkaido_east_2010_2025_1km.parquet")
FORTY_URL = ("https://huggingface.co/datasets/yuiseki/forty-hokkaido-east-2020/"
             f"resolve/{FORTY_REV}/data/parquet/forty_east_hokkaido_2020.parquet")


def overlap_records(cells, types):
    """Area overlay with an R-tree; cells and types contain projected geometries."""
    geometries = [item[2] for item in types]
    index = STRtree(geometries)
    areas, centers = {}, {}
    for row, col, geom in cells:
        covered = forest = 0.0
        positive = 0
        center_codes = []
        center = geom.centroid
        for ix in index.query(geom):
            i = int(ix)
            area = geom.intersection(geometries[i]).area
            if area > 0:
                positive += 1
                covered += area
                if types[i][1] in (1, 2, 3):
                    forest += area
            if geometries[i].intersects(center):
                center_codes.append(types[i][1])
        areas[(row, col)] = (geom.area, covered, forest, positive)
        centers[(row, col)] = center_codes
    return areas, centers


def eligible(record, forest_min=None, uncertainty_cap=None, cover_min=0.95, pixels_min=80):
    if record["cover_frac"] < cover_min or record["valid_pixels_2010"] < pixels_min:
        return False
    if record["valid_pixels_2025"] < pixels_min or record["drop"] <= 0:
        return False
    if forest_min is not None and record["forest_frac"] < forest_min:
        return False
    if uncertainty_cap is not None and record["uncertainty_mean_2025_mg_ha"] > uncertainty_cap:
        return False
    return True


def ranked_ids(records, k=20, forest_min=None, uncertainty_cap=None, cover_min=0.95, pixels_min=80):
    selected = (r for r in records if eligible(r, forest_min, uncertainty_cap, cover_min, pixels_min))
    ordered = sorted(selected, key=lambda r: (-r["drop"], r["cell_row"], r["cell_col"]))
    return [(r["cell_row"], r["cell_col"]) for r in ordered[:k]]


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty percentile input")
    pos = (len(ordered) - 1) * fraction
    lo = int(pos)
    return ordered[lo] + (ordered[min(lo + 1, len(ordered) - 1)] - ordered[lo]) * (pos - lo)


def main():
    con = duckdb.connect()
    con.execute("LOAD spatial")
    input_counts = {
        "ctrees": con.execute("SELECT count(*) FROM read_parquet(?)", [CTREES_URL]).fetchone()[0],
        "forty": con.execute("SELECT count(*) FROM read_parquet(?)", [FORTY_URL]).fetchone()[0],
    }
    type_rows = con.execute("""SELECT fid, class_code,
        ST_AsWKB(ST_Transform(geometry, 'EPSG:32655', 'EPSG:6933', always_xy := true))
        FROM read_parquet(?)""", [FORTY_URL]).fetchall()
    types = [(fid, klass, from_wkb(wkb)) for fid, klass, wkb in type_rows]
    west = min(g.bounds[0] for _, _, g in types)
    south = min(g.bounds[1] for _, _, g in types)
    east = max(g.bounds[2] for _, _, g in types)
    north = max(g.bounds[3] for _, _, g in types)
    type_window = box(west, south, east, north)
    raw_all = con.execute("""SELECT cell_row, cell_col,
        agb_mean_2010_mg_ha, agb_mean_2025_mg_ha,
        uncertainty_mean_2010_mg_ha, uncertainty_mean_2025_mg_ha,
        valid_pixels_2010, valid_pixels_2025,
        ST_X(ST_Centroid(geometry)) lon, ST_Y(ST_Centroid(geometry)) lat,
        ST_AsWKB(ST_Transform(geometry, 'EPSG:4326', 'EPSG:6933', always_xy := true))
        FROM read_parquet(?) ORDER BY cell_row,cell_col""", [CTREES_URL]).fetchall()
    all_cells = [(row, from_wkb(row[10])) for row in raw_all]
    selected = [(row, geom) for row, geom in all_cells if geom.intersects(type_window)]
    cells = [(row[0], row[1], geom) for row, geom in selected]
    spatial_checks = {
        "ctrees_invalid": sum(not geom.is_valid for _, geom in all_cells),
        "forty_invalid": sum(not geom.is_valid for _, _, geom in types),
        "ctrees_duplicate_keys": len(all_cells) - len({(row[0], row[1]) for row, _ in all_cells}),
        "forty_duplicate_keys": len(types) - len({fid for fid, _, _ in types}),
    }
    if any(spatial_checks.values()):
        raise RuntimeError(f"input geometry/key audit failed: {spatial_checks}")
    metrics, center_classes = overlap_records(cells, types)
    if any(covered > total * 1.01 for total, covered, _, _ in metrics.values()):
        raise RuntimeError("classified area exceeds cell area by >1%")
    records = []
    for row, _ in selected:
        a = metrics[(row[0], row[1])]
        records.append({
            "cell_row": row[0], "cell_col": row[1],
            "agb_2010": row[2], "agb_2025": row[3], "drop": row[2] - row[3],
            "uncertainty_mean_2010_mg_ha": row[4], "uncertainty_mean_2025_mg_ha": row[5],
            "valid_pixels_2010": row[6], "valid_pixels_2025": row[7],
            "lon": row[8], "lat": row[9],
            "cell_area_m2": a[0], "cover_frac": a[1] / a[0],
            "forest_frac": a[2] / a[0], "positive_intersections": a[3],
        })
    # Point assignment is a sensitivity check, not an area surrogate.
    for record in records:
        classes = center_classes.get((record["cell_row"], record["cell_col"]), [])
        record["center_class_count"] = len(classes)
        record["center_forest"] = len(classes) == 1 and classes[0] in (1, 2, 3)

    base = ranked_ids(records, 20)
    main_ids = ranked_ids(records, 20, forest_min=0.8)
    main_population = [r for r in records if eligible(r, forest_min=0.8)]
    cap = percentile([r["uncertainty_mean_2025_mg_ha"] for r in main_population], 0.75)
    variants = {
        "raw": base,
        "forest_0_5": ranked_ids(records, 20, forest_min=0.5),
        "forest_0_8_main": main_ids,
        "forest_0_9": ranked_ids(records, 20, forest_min=0.9),
        "forest_center": ranked_ids([r for r in records if r["center_forest"]], 20),
        "uncertainty_p75": ranked_ids(records, 20, forest_min=0.8, uncertainty_cap=cap),
        "pixels_100": ranked_ids(records, 20, forest_min=0.8, pixels_min=100),
        "forest_0_8_top50": ranked_ids(records, 50, forest_min=0.8),
    }
    if len(main_ids) < 20:
        raise RuntimeError("fewer than 20 candidates in main universe")
    lookup = {(r["cell_row"], r["cell_col"]): r for r in records}
    stable = set(main_ids).intersection(*(set(v) for k, v in variants.items()
                                               if k not in ("raw", "forest_0_8_main", "forest_0_8_top50")))
    summary = {
        "date": str(date.today()), "duckdb_version": duckdb.__version__,
        "inputs": {"ctrees": {"url": CTREES_URL, "revision": CTREES_REV, "rows": input_counts["ctrees"]},
                   "forty": {"url": FORTY_URL, "revision": FORTY_REV, "rows": input_counts["forty"]}},
        "spatial_checks": spatial_checks,
        "ctrees_bbox_candidates": len(records),
        "area_intersections_positive": sum(r["positive_intersections"] for r in records),
        "cells_without_area_overlap": sum(r["positive_intersections"] == 0 for r in records),
        "cells_covered_95pct": sum(r["cover_frac"] >= 0.95 for r in records),
        "cells_forest_80pct": sum(r["forest_frac"] >= 0.8 and r["cover_frac"] >= 0.95 for r in records),
        "cells_eligible_main": len(main_population),
        "cells_pixel_counts_differ": sum(r["valid_pixels_2010"] != r["valid_pixels_2025"] for r in records),
        "cells_center_multiple": sum(r["center_class_count"] > 1 for r in records),
        "cells_center_unassigned": sum(r["center_class_count"] == 0 for r in records),
        "uncertainty_p75_mg_ha": cap,
        "variants": {name: [{"cell_row": r, "cell_col": c} for r, c in ids] for name, ids in variants.items()},
        "overlap_main": {name: len(set(ids) & set(main_ids)) for name, ids in variants.items()
                         if name != "forest_0_8_top50"},
        "stable_main_count": len(stable),
        "stable_main_ids": [{"cell_row": r, "cell_col": c} for r, c in sorted(stable)],
        "main_top20": [{k: lookup[id][k] for k in (
            "cell_row", "cell_col", "lon", "lat", "drop", "forest_frac", "cover_frac",
            "valid_pixels_2010", "valid_pixels_2025", "uncertainty_mean_2025_mg_ha")}
            for id in main_ids],
        "interpretation": "Derived screening of model estimates, not observed forest loss or carbon emissions.",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "cell_metrics.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in (
        "ctrees_bbox_candidates", "cells_without_area_overlap", "cells_covered_95pct",
        "cells_forest_80pct", "cells_eligible_main", "cells_pixel_counts_differ",
        "overlap_main", "stable_main_count")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

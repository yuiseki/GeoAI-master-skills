"""Join fixed WorldCover 2021 class counts to the already analyzed 2020 mesh results.

uv run --no-project --with duckdb --with numpy --with pyproj python3 \
  projects/__exp/japan-grid-population-audit/scripts/run_landcover.py
"""

import csv
import gzip
import json
from itertools import pairwise
from urllib.request import urlopen

import duckdb
import numpy as np
import pyproj
from analyze import Tile, aggregate_landcover, assemble_grid, mesh_bounds
from run_analysis import ARTIFACTS, PROJECT, WORLD_COVER_SHA

ROOT = f"https://huggingface.co/datasets/yuiseki/esa-worldcover-tokyo-2021-100m/resolve/{WORLD_COVER_SHA}/data/parquet"
CLASS_CODES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)


def read_cover():
    with urlopen(ROOT + "/profile.json", timeout=120) as response:
        profile = json.load(response)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs")
    url = ROOT + "/esa_worldcover_tokyo_2021_v200_100m.parquet"
    cols = ", ".join(
        ["cell_row", "cell_col", "valid_pixels"]
        + [f"pixels_{code}" for code in CLASS_CODES]
    )
    data = con.execute(f"SELECT {cols} FROM read_parquet(?)", [url]).fetchnumpy()
    gt = profile["output_geotransform"]
    if gt[2] != 0 or gt[4] != 0 or gt[1] <= 0 or gt[5] >= 0:
        raise ValueError("WorldCover grid is rotated or reversed")
    shape = (600, 600)
    rows, cols = data["cell_row"], data["cell_col"]
    valid = assemble_grid(rows, cols, data["valid_pixels"], shape)
    stack = np.stack(
        [
            assemble_grid(rows, cols, data[f"pixels_{code}"], shape)
            for code in CLASS_CODES
        ],
        axis=-1,
    )
    if not np.allclose(stack.sum(axis=-1), valid, rtol=0, atol=0):
        raise ValueError("class counts do not sum to valid pixels")
    if int(valid.sum()) != profile["aggregation"]["valid_pixels"]:
        raise ValueError("valid pixel total differs from source profile")
    for index, code in enumerate(CLASS_CODES):
        expected = profile["aggregation"]["output_class_pixel_counts"][str(code)]
        if int(stack[:, :, index].sum()) != expected:
            raise ValueError(f"class {code} total differs from source profile")
    tile = Tile("worldcover_100m", gt[0], gt[3], gt[1], -gt[5], valid)
    return (
        tile,
        stack,
        {
            "cells": int(valid.size),
            "valid_pixels": int(valid.sum()),
            "class_pixel_totals": {
                str(code): int(stack[:, :, i].sum())
                for i, code in enumerate(CLASS_CODES)
            },
            "bounds": tile.bounds,
            "url": url,
        },
    )


def read_population_meshes():
    source = ARTIFACTS / "full-mesh-results.csv.gz"
    if not source.exists():
        raise FileNotFoundError("run the full GHSL/census analysis before WorldCover")
    with gzip.open(source, "rt", encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream)


def describe_group(rows):
    if not rows:
        return {"n": 0, "median_abs_log1p_error": None, "median_abs_error_people": None}
    return {
        "n": len(rows),
        "median_abs_log1p_error": float(
            np.median([row["abs_log1p_error"] for row in rows])
        ),
        "median_abs_error_people": float(
            np.median([row["abs_error_people"] for row in rows])
        ),
        "census_population_sum": int(sum(row["census_population"] for row in rows)),
    }


def binned(rows, field, boundaries):
    output = []
    for lo, hi in pairwise(boundaries):
        selected = [row for row in rows if lo <= row[field] < hi]
        output.append(
            {"min_inclusive": lo, "max_exclusive": hi, **describe_group(selected)}
        )
    return output


def run():
    tile, stack, data_audit = read_cover()
    selected = []
    audit = {
        "input_population_meshes": 0,
        "pilot_excluded": 0,
        "outside_cover_rectangle": 0,
        "partial_cover": 0,
        "zero_cover_pixels": 0,
        "included": 0,
    }
    for row in read_population_meshes():
        audit["input_population_meshes"] += 1
        if row["pilot_block"] == "True":
            audit["pilot_excluded"] += 1
            continue
        bounds = mesh_bounds(row["mesh_code"])
        if not (
            bounds[0] >= tile.bounds[0]
            and bounds[1] >= tile.bounds[1]
            and bounds[2] <= tile.bounds[2]
            and bounds[3] <= tile.bounds[3]
        ):
            audit["outside_cover_rectangle"] += 1
            continue
        cover = aggregate_landcover(bounds, tile, stack)
        if cover["coverage"] < 1 - 1e-8:
            audit["partial_cover"] += 1
            continue
        if cover["shares"] is None:
            audit["zero_cover_pixels"] += 1
            continue
        census = int(row["census_population"])
        ghsl = float(row["ghsl_area"])
        selected.append(
            {
                "mesh_code": row["mesh_code"],
                "prefecture": row["prefecture"],
                "lon": float(row["lon"]),
                "lat": float(row["lat"]),
                "census_population": census,
                "ghsl_area": ghsl,
                "built_share": cover["shares"][CLASS_CODES.index(50)],
                "mixedness": cover["mixedness"],
                "valid_pixels": cover["valid_pixels"],
                "abs_error_people": abs(ghsl - census),
                "abs_log1p_error": abs(float(np.log1p(ghsl) - np.log1p(census))),
            }
        )
        audit["included"] += 1
    if (
        sum(
            audit[k]
            for k in (
                "pilot_excluded",
                "outside_cover_rectangle",
                "partial_cover",
                "zero_cover_pixels",
                "included",
            )
        )
        != audit["input_population_meshes"]
    ):
        raise ValueError("population mesh accounting failed")
    if not selected:
        raise ValueError("WorldCover has no full census meshes")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with gzip.open(
        ARTIFACTS / "tokyo-landcover-mesh.csv.gz", "wt", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    summary = {
        "source_versions": {"worldcover": WORLD_COVER_SHA},
        "tools": {
            "duckdb": duckdb.__version__,
            "numpy": np.__version__,
            "pyproj": pyproj.__version__,
        },
        "data_audit": data_audit,
        "join_audit": audit,
        "outcome": "Absolute log1p difference in people, descriptive association only",
        "overall": describe_group(selected),
        "built_share_bins": binned(
            selected, "built_share", (0, 0.25, 0.5, 0.75, 1.0000001)
        ),
        "mixedness_bins": binned(selected, "mixedness", (0, 0.1, 0.2, 0.4, 1.0000001)),
        "built_share_bins_min100": binned(
            [r for r in selected if r["census_population"] >= 100],
            "built_share",
            (0, 0.25, 0.5, 0.75, 1.0000001),
        ),
        "mixedness_bins_min100": binned(
            [r for r in selected if r["census_population"] >= 100],
            "mixedness",
            (0, 0.1, 0.2, 0.4, 1.0000001),
        ),
        "artifact": str(
            (ARTIFACTS / "tokyo-landcover-mesh.csv.gz").relative_to(PROJECT.parents[2])
        ),
    }
    output = PROJECT / "outputs" / "landcover-summary.json"
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "summary": str(output),
                "join_audit": audit,
                "overall": summary["overall"],
                "built_share_bins": summary["built_share_bins"],
                "mixedness_bins": summary["mixedness_bins"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

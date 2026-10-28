"""Run the preregistered census-vs-GHSL grid comparison.

uv run --no-project --with duckdb --with numpy --with pyproj python3 \
  projects/__exp/japan-grid-population-audit/scripts/run_analysis.py --scope pilot
uv run --no-project --with duckdb --with numpy --with pyproj python3 \
  projects/__exp/japan-grid-population-audit/scripts/run_analysis.py --scope full

Outputs are generated analysis artifacts, never hand-entered paper numbers.
"""

import argparse
import csv
import gzip
import json
import math
from pathlib import Path
from urllib.request import urlopen

import duckdb
import numpy as np
import pyproj
from analyze import (
    Tile,
    aggregate_census_rows,
    assemble_grid,
    estimate_mesh,
    mesh_bounds,
    ranked_overlap,
)

PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT.parents[2] / "artifacts" / PROJECT.parent.name / PROJECT.name
CENSUS_SHA = "6c486c8649484e09e549c0c99b5fa89b4f416edb"
GHSL_SHA = "4ee767429ee03ea47a9003c547f92c320474e350"
WORLD_COVER_SHA = "6f006f64483b65b20f06c775b87db7a8d57a6fda"
CENSUS_URL = f"https://huggingface.co/datasets/yuiseki/estat-census-mesh-2020/resolve/{CENSUS_SHA}/parquet/T001140.parquet"
GHSL_ROOT = f"https://huggingface.co/datasets/yuiseki/ghsl-japan-core-2020-30arcsec/resolve/{GHSL_SHA}/data/parquet"
GHSL_CODES = ("R5_C32", "R5_C33", "R6_C31", "R6_C32", "R6_C33")
PILOT_PREFIX = "533946"


def connect() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("INSTALL httpfs; LOAD httpfs")
    connection.execute("INSTALL spatial; LOAD spatial")
    connection.execute("SET threads=4")
    connection.execute("SET memory_limit='4GB'")
    connection.execute("SET geometry_always_xy=true")
    return connection


def read_json(url: str) -> dict:
    with urlopen(url, timeout=120) as response:
        return json.load(response)


def read_census(connection: duckdb.DuckDBPyConnection):
    rows = connection.execute(
        "SELECT prefecture, KEY_CODE, T001140001 FROM read_parquet(?)", [CENSUS_URL]
    ).fetchall()
    values, audit = aggregate_census_rows(rows)
    pref_values = {}
    for prefecture, code, raw in rows:
        pref_values[(code, prefecture)] = pref_values.get((code, prefecture), 0) + int(
            raw
        )
    by_code = {}
    for (code, prefecture), count in pref_values.items():
        if code not in by_code or (count, -int(prefecture)) > (
            by_code[code][0],
            -int(by_code[code][1]),
        ):
            by_code[code] = (count, prefecture)
    prefectures = {code: row[1] for code, row in by_code.items()}
    if audit["input_rows"] != 177861 or audit["population_total"] != 126146099:
        raise ValueError(f"census frozen version disagrees with measured card: {audit}")
    return values, prefectures, audit


def read_tiles(connection: duckdb.DuckDBPyConnection, codes: tuple[str, ...]):
    profile = read_json(f"{GHSL_ROOT}/profile.json")
    entries = profile["products"]["population"]["tiles"]
    tiles = []
    audit = {}
    for code in codes:
        entry = entries[code]
        url = f"{GHSL_ROOT}/population/{code}.parquet"
        data = connection.execute(
            "SELECT cell_row, cell_col, population_estimate FROM read_parquet(?)", [url]
        ).fetchnumpy()
        grid = assemble_grid(
            data["cell_row"],
            data["cell_col"],
            data["population_estimate"],
            (entry["rows"], entry["cols"]),
        )
        if np.any(grid < 0):
            raise ValueError(f"negative estimated population in {code}")
        if not np.isclose(grid.sum(), entry["value_sum"], rtol=1e-9):
            raise ValueError(f"population sum disagrees with source profile: {code}")
        transform = entry["geotransform"]
        if (
            transform[2] != 0
            or transform[4] != 0
            or transform[1] <= 0
            or transform[5] >= 0
        ):
            raise ValueError(f"rotated or reversed grid: {code}")
        observed = connection.execute(
            "SELECT ST_XMin(geometry), ST_YMin(geometry), ST_XMax(geometry), ST_YMax(geometry) "
            "FROM read_parquet(?) WHERE cell_row=0 AND cell_col=0",
            [url],
        ).fetchone()
        expected = (
            transform[0],
            transform[3] + transform[5],
            transform[0] + transform[1],
            transform[3],
        )
        if observed is None or not np.allclose(observed, expected, rtol=0, atol=1e-6):
            raise ValueError(
                f"geometry disagrees with grid profile: {code}: {observed}, {expected}"
            )
        tile = Tile(code, transform[0], transform[3], transform[1], -transform[5], grid)
        tiles.append(tile)
        audit[code] = {
            "rows": int(grid.size),
            "zero_cells": int(np.count_nonzero(grid == 0)),
            "population_sum": float(grid.sum()),
            "bounds": tile.bounds,
            "geometry_sample_bounds": observed,
            "url": url,
        }
    return tuple(tiles), audit


def metrics(rows: list[dict], field: str) -> dict:
    census = np.array([row["census_population"] for row in rows], dtype=np.float64)
    estimate = np.array([row[field] for row in rows], dtype=np.float64)
    delta = estimate - census
    return {
        "n": len(rows),
        "census_sum": float(census.sum()),
        "estimate_sum": float(estimate.sum()),
        "estimate_to_census_ratio": float(estimate.sum() / census.sum()),
        "bias_mean_people": float(delta.mean()),
        "mae_people": float(np.abs(delta).mean()),
        "median_abs_error_people": float(np.median(np.abs(delta))),
        "p90_abs_error_people": float(np.percentile(np.abs(delta), 90)),
        "median_abs_log1p_error": float(
            np.median(np.abs(np.log1p(estimate) - np.log1p(census)))
        ),
    }


def ranking_rows(rows: list[dict], fractions=(0.05, 0.10, 0.20)):
    census = {row["mesh_code"]: row["census_population"] for row in rows}
    output = []
    for fraction in fractions:
        k = max(1, math.ceil(len(rows) * fraction))
        for method in ("ghsl_area", "ghsl_center"):
            estimate = {row["mesh_code"]: row[method] for row in rows}
            result = ranked_overlap(census, estimate, k)
            output.append(
                {
                    "fraction": fraction,
                    "method": method,
                    "eligible_meshes": len(rows),
                    "k": k,
                    "overlap": result["overlap"],
                    "recall": result["recall"],
                    "census_population_recovered": result[
                        "census_population_recovered"
                    ],
                }
            )
    return output


def run(scope: str) -> dict:
    connection = connect()
    census, prefectures, census_audit = read_census(connection)
    codes = ("R6_C32",) if scope == "pilot" else GHSL_CODES
    tiles, tile_audit = read_tiles(connection, codes)
    rows = []
    coverage_counts = {"full_positive": 0, "full_zero": 0, "partial": 0, "outside": 0}
    excluded_census_population = {"partial": 0, "outside": 0, "full_zero": 0}
    for index, (code, population) in enumerate(sorted(census.items())):
        if scope == "pilot" and not code.startswith(PILOT_PREFIX):
            continue
        estimate = estimate_mesh(mesh_bounds(code), tiles)
        if estimate.coverage < 1e-10:
            status = "outside"
        elif estimate.coverage < 1 - 1e-8:
            status = "partial"
        elif population == 0:
            status = "full_zero"
        else:
            status = "full_positive"
        coverage_counts[status] += 1
        if status in excluded_census_population:
            excluded_census_population[status] += population
        if status == "full_positive":
            bounds = mesh_bounds(code)
            rows.append(
                {
                    "mesh_code": code,
                    "prefecture": prefectures[code],
                    "lon": (bounds[0] + bounds[2]) / 2,
                    "lat": (bounds[1] + bounds[3]) / 2,
                    "census_population": population,
                    "ghsl_area": estimate.area_population,
                    "ghsl_center": estimate.center_population,
                    "source_cells": estimate.overlap_cells,
                    "coverage": estimate.coverage,
                    "pilot_block": code.startswith(PILOT_PREFIX),
                }
            )
        if index and index % 20000 == 0:
            print(f"examined {index}/{len(census)} census meshes", flush=True)
    evaluation = (
        rows if scope == "pilot" else [row for row in rows if not row["pilot_block"]]
    )
    if not evaluation:
        raise ValueError("no fully covered inhabited meshes in evaluation")
    output_dir = PROJECT / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACTS / f"{scope}-mesh-results.csv.gz"
    with gzip.open(artifact_path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "scope": scope,
        "source_versions": {
            "census": CENSUS_SHA,
            "ghsl": GHSL_SHA,
            "worldcover_not_used_here": WORLD_COVER_SHA,
        },
        "tools": {
            "duckdb": duckdb.__version__,
            "numpy": np.__version__,
            "pyproj": pyproj.__version__,
        },
        "crs": {
            "input": "JGD2011 mesh code and GHSL EPSG:4326 lon-lat",
            "area": "EPSG:6933, always_xy",
        },
        "census_audit": census_audit,
        "ghsl_tiles": tile_audit,
        "coverage_counts": coverage_counts,
        "excluded_census_population": excluded_census_population,
        "fully_covered_positive_meshes": len(rows),
        "pilot_block_meshes": sum(row["pilot_block"] for row in rows),
        "evaluation_meshes": len(evaluation),
        "artifact": str(artifact_path.relative_to(PROJECT.parents[2])),
        "metrics": {
            field: metrics(evaluation, field) for field in ("ghsl_area", "ghsl_center")
        },
        "rankings": ranking_rows(evaluation),
        "low_population": {
            str(threshold): sum(
                row["census_population"] < threshold for row in evaluation
            )
            for threshold in (100, 1000)
        },
    }
    if scope == "pilot":
        subset = {row["mesh_code"]: row["census_population"] for row in evaluation}
        summary["pilot_top20"] = {
            field: {
                key: value
                for key, value in ranked_overlap(
                    subset, {row["mesh_code"]: row[field] for row in evaluation}, 20
                ).items()
                if key in ("overlap", "recall", "census_population_recovered")
            }
            for field in ("ghsl_area", "ghsl_center")
        }
    else:
        per_pref = []
        for prefecture in sorted({row["prefecture"] for row in evaluation}):
            subset_rows = [row for row in evaluation if row["prefecture"] == prefecture]
            if len(subset_rows) < 20:
                continue
            row = {
                "prefecture": prefecture,
                "meshes": len(subset_rows),
                "area_mae_people": metrics(subset_rows, "ghsl_area")["mae_people"],
            }
            for item in ranking_rows(subset_rows, (0.10,)):
                row[item["method"] + "_recall10"] = item["recall"]
            per_pref.append(row)
        summary["prefecture_summary"] = per_pref
    summary_path = output_dir / f"{scope}-summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "summary": str(summary_path),
                "coverage": coverage_counts,
                "eligible": len(evaluation),
                "metrics": summary["metrics"],
                "rankings": summary["rankings"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("pilot", "full"), required=True)
    args = parser.parse_args()
    run(args.scope)

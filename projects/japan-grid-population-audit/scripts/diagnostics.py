"""Diagnose the saved Tokyo land-cover comparison, without rereading remote inputs.

uv run --no-project --with numpy --with scipy --with scikit-learn python3 \
  projects/japan-grid-population-audit/scripts/diagnostics.py
"""

import csv
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parents[1]
ARTIFACT = REPOSITORY / "artifacts" / PROJECT.name / "tokyo-landcover-mesh.csv.gz"


def mesh_indices(code: str) -> tuple[int, int]:
    if len(code) != 8 or not code.isascii() or not code.isdigit():
        raise ValueError(f"invalid third-mesh code: {code!r}")
    return int(code[:2]) * 80 + int(code[4]) * 10 + int(code[6]), int(
        code[2:4]
    ) * 80 + int(code[5]) * 10 + int(code[7])


def pearson(x, y) -> float:
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if (
        len(a) != len(b)
        or len(a) < 2
        or not np.all(np.isfinite(a))
        or not np.all(np.isfinite(b))
    ):
        raise ValueError("correlation needs at least two finite paired values")
    if np.ptp(a) == 0 or np.ptp(b) == 0:
        raise ValueError("correlation has a constant variable")
    return float(np.corrcoef(a, b)[0, 1])


def coarsen(rows: list[dict], scale: int, shift: int = 0) -> list[dict]:
    if scale < 1 or shift < 0 or shift >= scale:
        raise ValueError("invalid scale or shift")
    groups = {}
    seen = set()
    for row in rows:
        key = (row["grid_row"], row["grid_col"])
        if key in seen:
            raise ValueError("duplicate mesh index")
        seen.add(key)
        group_key = ((key[0] + shift) // scale, (key[1] + shift) // scale)
        groups.setdefault(group_key, []).append(row)
    complete = []
    for (grid_row, grid_col), group in sorted(groups.items()):
        if len(group) != scale * scale:
            continue
        count = sum(row["census_population"] for row in group)
        estimated = sum(row["ghsl_area"] for row in group)
        valid = sum(row["valid_pixels"] for row in group)
        if count < 0 or estimated < 0 or valid <= 0:
            raise ValueError("invalid population or coverage")
        built = sum(row["built_share"] * row["valid_pixels"] for row in group) / valid
        complete.append(
            {
                "grid_row": grid_row,
                "grid_col": grid_col,
                "census_population": count,
                "ghsl_area": estimated,
                "built_share": built,
                "valid_pixels": valid,
                "abs_log1p_error": abs(math.log1p(estimated) - math.log1p(count)),
            }
        )
    return complete


def read_rows() -> list[dict]:
    if not ARTIFACT.exists():
        raise FileNotFoundError(f"run_landcover.py must run first: {ARTIFACT}")
    rows = []
    with gzip.open(ARTIFACT, "rt", encoding="utf-8", newline="") as stream:
        for raw in csv.DictReader(stream):
            grid_row, grid_col = mesh_indices(raw["mesh_code"])
            rows.append(
                {
                    "mesh_code": raw["mesh_code"],
                    "grid_row": grid_row,
                    "grid_col": grid_col,
                    "lon": float(raw["lon"]),
                    "lat": float(raw["lat"]),
                    "census_population": int(raw["census_population"]),
                    "ghsl_area": float(raw["ghsl_area"]),
                    "built_share": float(raw["built_share"]),
                    "valid_pixels": float(raw["valid_pixels"]),
                    "abs_log1p_error": float(raw["abs_log1p_error"]),
                }
            )
    if len(rows) != 1899 or len({row["mesh_code"] for row in rows}) != len(rows):
        raise ValueError("land-cover rows disagree with frozen analysis output")
    return rows


def run() -> dict:
    rows = read_rows()
    # The existing skill's tested kNN/Moran implementation uses spherical distances.
    sys.path.insert(
        0,
        str(REPOSITORY / ".agents" / "skills" / "spatial-autocorrelation" / "scripts"),
    )
    from spatial_autocorrelation import knn_neighbors, moran

    lon = np.array([row["lon"] for row in rows])
    lat = np.array([row["lat"] for row in rows])
    result = {
        "input_artifact": str(ARTIFACT.relative_to(REPOSITORY)),
        "analysis": "exploratory diagnostic after main land-cover bins; not a causal or predictive test",
        "outcome": "absolute difference between log1p GHSL and log1p census population, people",
        "spatial_weights": "spherical k-nearest meshes; row-standardized; k=4,8,12; zero islands by construction",
        "moran_permutations": 999,
        "moran_seed": 0,
        "moran": [],
        "grid_sweep": [],
    }
    for k in (4, 8, 12):
        neighbors = knn_neighbors(lon, lat, k)
        for field in ("built_share", "abs_log1p_error"):
            values = [row[field] for row in rows]
            result["moran"].append(
                {"k": k, "field": field, **moran(values, neighbors, 999, 0)}
            )
    for scale in (1, 2, 4, 8):
        for shift in (0,) if scale == 1 else (0, scale // 2):
            aggregated = coarsen(rows, scale, shift)
            if len(aggregated) < 4:
                raise ValueError(
                    f"too few complete grid blocks at scale {scale}, shift {shift}"
                )
            result["grid_sweep"].append(
                {
                    "scale": scale,
                    "shift": shift,
                    "complete_blocks": len(aggregated),
                    "represented_meshes": len(aggregated) * scale * scale,
                    "r_built_vs_abs_log_error": pearson(
                        [row["built_share"] for row in aggregated],
                        [row["abs_log1p_error"] for row in aggregated],
                    ),
                }
            )
    output = PROJECT / "outputs" / "spatial-diagnostics.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()

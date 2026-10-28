"""Sensitivity of top-population candidates to an eligibility population floor.

uv run --no-project --with numpy --with pyproj python3 \
  projects/__exp/japan-grid-population-audit/scripts/population_sensitivity.py
"""

import csv
import gzip
import json
import math
from pathlib import Path

from analyze import ranked_overlap

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parents[2]
SOURCE = REPOSITORY / "artifacts" / PROJECT.parent.name / PROJECT.name / "full-mesh-results.csv.gz"


def compare_cutoff(rows: list[dict], min_people: int, fraction: float = 0.1) -> dict:
    if min_people < 0 or not (0 < fraction <= 1):
        raise ValueError("invalid cutoff or selection fraction")
    selected = [row for row in rows if row["census_population"] >= min_people]
    if not selected:
        raise ValueError("no eligible meshes")
    census = {row["mesh_code"]: row["census_population"] for row in selected}
    if len(census) != len(selected):
        raise ValueError("duplicate mesh code")
    k = math.ceil(len(selected) * fraction)
    rankings = []
    for method in ("ghsl_area", "ghsl_center"):
        estimate = {row["mesh_code"]: row[method] for row in selected}
        result = ranked_overlap(census, estimate, k)
        rankings.append(
            {
                "method": method,
                "overlap": result["overlap"],
                "recall": result["recall"],
                "census_population_recovered": result["census_population_recovered"],
            }
        )
    return {
        "min_census_people_inclusive": min_people,
        "fraction": fraction,
        "eligible_meshes": len(selected),
        "excluded_meshes": len(rows) - len(selected),
        "k": k,
        "rankings": rankings,
    }


def run() -> dict:
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"run_analysis.py --scope full must run first: {SOURCE}"
        )
    rows = []
    pilot = 0
    with gzip.open(SOURCE, "rt", encoding="utf-8", newline="") as stream:
        for raw in csv.DictReader(stream):
            if raw["pilot_block"] == "True":
                pilot += 1
                continue
            rows.append(
                {
                    "mesh_code": raw["mesh_code"],
                    "census_population": int(raw["census_population"]),
                    "ghsl_area": float(raw["ghsl_area"]),
                    "ghsl_center": float(raw["ghsl_center"]),
                }
            )
    if len(rows) != 174900 or pilot != 100:
        raise ValueError("full mesh artifact disagrees with saved main analysis")
    result = {
        "input_artifact": str(SOURCE.relative_to(REPOSITORY)),
        "pilot_excluded": pilot,
        "thresholds": [compare_cutoff(rows, people) for people in (0, 100, 1000)],
    }
    output = PROJECT / "outputs" / "population-sensitivity.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()

"""Summarize proximity to mapped records without interpreting it as coverage."""

import csv
import json
from pathlib import Path


ROOT = Path("projects/_telecom/south-sudan-unmiss-telecom-gap")
CURRENT_INPUT = ROOT / "outputs/unmiss_record_proximity.csv"
LEGACY_INPUT = ROOT / "outputs/legacy_unmiss_site_cellular_distance.csv"
INPUT = CURRENT_INPUT if CURRENT_INPUT.exists() else LEGACY_INPUT
OUTPUT = ROOT / "outputs/observation_proximity_audit.json"


def main():
    with INPUT.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    def value(row, current, legacy):
        return row[current] if current in row else row[legacy]

    thresholds = (10, 25)
    metrics = {
        "deployment_coordinate_clusters": len(rows),
        "deployment_records_in_clusters": sum(int(value(row, "deployment_records_at_coordinate", "deployed_units")) for row in rows),
        "thresholds_km": list(thresholds),
        "within_threshold_counts": {
            "ookla_2024_q2_mobile_tile_centroid": {
                str(t): sum(float(value(r, "dist_ookla_tile_km", "dist_ookla_km")) <= t for r in rows) for t in thresholds
            },
            "osm_mapped_power_related_point": {
                str(t): sum(float(value(r, "dist_osm_power_related_point_km", "dist_power_gen_km")) <= t for r in rows) for t in thresholds
            },
            "osm_mapped_power_line": {
                str(t): sum(float(r["dist_power_line_km"]) <= t for r in rows) for t in thresholds
            },
        },
        "interpretation": (
            "Distances are proximity to records in the named datasets, not service, operational access, "
            "or coverage. OpenCelliD distances are not used for these counts; see the dedicated "
            "opencellid_record_proximity.csv, calculated on the WGS84 ellipsoid."
        ),
        "inputs": [str(INPUT)],
    }
    OUTPUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

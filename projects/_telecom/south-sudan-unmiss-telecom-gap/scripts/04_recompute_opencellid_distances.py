"""Recompute nearest OpenCelliD record distances on the WGS84 ellipsoid.

The source CSV must be filtered from the pinned OpenCelliD snapshot to MCC 659.
This reports proximity to database records, never radio coverage.
"""

import argparse
import csv
import json
from pathlib import Path

from spatial_helpers import geodesic_distance_km


ROOT = Path("projects/_telecom/south-sudan-unmiss-telecom-gap")
CURRENT_SITE_CSV = ROOT / "outputs/unmiss_record_proximity.csv"
LEGACY_SITE_CSV = ROOT / "outputs/legacy_unmiss_site_cellular_distance.csv"
OUTPUT_CSV = ROOT / "outputs/opencellid_record_proximity.csv"
OUTPUT_JSON = ROOT / "outputs/opencellid_record_proximity_summary.json"
THRESHOLDS_KM = (10, 25)


def nearest_record(site, cells, radio=None):
    candidates = [cell for cell in cells if radio is None or cell["radio"] == radio]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda cell: geodesic_distance_km(
            float(site["site_lon"]), float(site["site_lat"]),
            float(cell["lon"]), float(cell["lat"]),
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells-csv", required=True, type=Path,
                        help="MCC 659 rows (radio,lon,lat,range,samples) from pinned snapshot")
    args = parser.parse_args()
    site_csv = CURRENT_SITE_CSV if CURRENT_SITE_CSV.exists() else LEGACY_SITE_CSV
    with site_csv.open(encoding="utf-8", newline="") as stream:
        sites = list(csv.DictReader(stream))
    with args.cells_csv.open(encoding="utf-8", newline="") as stream:
        cells = list(csv.DictReader(stream))

    rows = []
    for site in sites:
        result = {
            "map_text_hint": site.get("map_text_hint", site.get("site_name", "")),
            "deployment_records_at_coordinate": site.get("deployment_records_at_coordinate", site.get("deployed_units", "")),
            "longitude_wgs84": site["site_lon"],
            "latitude_wgs84": site["site_lat"],
        }
        for suffix, radio in (("any", None), ("lte", "LTE")):
            cell = nearest_record(site, cells, radio=radio)
            if cell is None:
                result[f"nearest_{suffix}_record_distance_km"] = ""
                result[f"nearest_{suffix}_record_radio"] = ""
                result[f"nearest_{suffix}_record_range_m"] = ""
                result[f"nearest_{suffix}_record_samples"] = ""
                continue
            distance = geodesic_distance_km(
                float(site["site_lon"]), float(site["site_lat"]),
                float(cell["lon"]), float(cell["lat"]),
            )
            result[f"nearest_{suffix}_record_distance_km"] = f"{distance:.3f}"
            result[f"nearest_{suffix}_record_radio"] = cell["radio"]
            result[f"nearest_{suffix}_record_range_m"] = cell.get("range", "")
            result[f"nearest_{suffix}_record_samples"] = cell.get("samples", "")
        rows.append(result)

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    distances = sorted(float(row["nearest_any_record_distance_km"]) for row in rows)
    summary = {
        "source_snapshot": "yuiseki/opencellid, revision 82e4acdb5ea93250ea6128ce08c03a4ca8870c88, 2026-10-06",
        "mcc": 659,
        "cell_records": len(cells),
        "deployment_coordinate_clusters": len(rows),
        "deployment_records_at_coordinate_clusters": sum(int(row["deployment_records_at_coordinate"]) for row in rows),
        "nearest_record_distance_km_median": round(distances[len(distances) // 2], 3),
        "nearest_record_distance_km_max": round(max(distances), 3),
        "clusters_with_record_within_km": {
            str(threshold): sum(distance <= threshold for distance in distances)
            for threshold in THRESHOLDS_KM
        },
        "interpretation": "Distance to a community-mapped cell record only; not evidence of active infrastructure, signal, or service availability.",
        "output_csv": str(OUTPUT_CSV),
    }
    OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

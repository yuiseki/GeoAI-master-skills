import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from spatial_helpers import geodesic_distance_km, within_distance

def test_summary_metrics_file():
    p = Path("projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/summary_metrics.json")
    assert p.exists()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    assert data["deployment_coordinate_clusters"] == 19
    assert data["deployment_records_on_2024_10_25_source_map"] == 77
    assert data["coordinate_clusters_with_ookla_2024_q2_tile_within_10km"] == 11
    assert "do not establish coverage" in data["interpretation_note"].lower()

def test_site_distance_csv():
    p = Path("projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/opencellid_record_proximity.csv")
    assert p.exists()
    df = pd.read_csv(p, encoding="utf-8")
    assert len(df) == 19
    assert "nearest_any_record_distance_km" in df.columns
    assert "has_cellular_coverage_10km" not in df.columns
    assert abs(float(df["nearest_any_record_distance_km"].median()) - 454.12) < 0.01


def test_geodesic_distance_is_in_kilometres():
    assert abs(geodesic_distance_km(0, 0, 1, 0) - 111.31949) < 0.001
    distances = geodesic_distance_km([0, 0], [0, 0], [1, 0], [0, 1])
    assert len(distances) == 2
    assert abs(distances[1] - 110.57439) < 0.001


def test_threshold_is_named_as_proximity_not_coverage():
    assert within_distance(9.99, 10) is True
    assert within_distance(10.01, 10) is False


def test_observation_audit_does_not_call_proximity_coverage():
    p = Path("projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/observation_proximity_audit.json")
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data["within_threshold_counts"]["ookla_2024_q2_mobile_tile_centroid"]["10"] == 11
    assert "not" in data["interpretation"].lower()

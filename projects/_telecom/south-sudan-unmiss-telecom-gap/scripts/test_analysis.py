import json
import pandas as pd
from pathlib import Path

def test_summary_metrics_file():
    p = Path("projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/summary_metrics.json")
    assert p.exists()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_unmiss_sites"] == 19
    assert data["total_unmiss_units"] == 77
    assert data["sites_without_cellular_10km"] == 18
    assert data["sites_without_lte_10km"] == 18
    assert data["pct_sites_without_cellular_10km"] == 94.74

def test_site_distance_csv():
    p = Path("projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_site_cellular_distance.csv")
    assert p.exists()
    df = pd.read_csv(p, encoding="utf-8")
    assert len(df) == 19
    # Juba should have cellular coverage within 10km
    juba = df[df["site_name"] == "Juba"]
    assert len(juba) == 1
    assert juba["has_cellular_coverage_10km"].values[0] == True
    # All other sites should be false
    non_juba = df[df["site_name"] != "Juba"]
    assert not non_juba["has_cellular_coverage_10km"].any()

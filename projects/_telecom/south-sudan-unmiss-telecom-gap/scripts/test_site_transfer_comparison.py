import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("site_transfer", Path(__file__).with_name("07_site_transfer_comparison.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_ideal_transfer_time_and_missing():
    assert module.transfer_minutes(10) == 4 / 3
    assert module.transfer_minutes(None) is None
    assert module.transfer_minutes(0) is None


def test_far_observation_is_not_converted_to_site_speed():
    row = {"nearest_tile_mean_download_mbps": 10, "nearest_tile_distance_km": 11}
    assert module.eligible_speed(row) is None
    row["nearest_tile_distance_km"] = 10
    assert module.eligible_speed(row) == 10

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("speed", Path(__file__).with_name("05_speed_comparison.py"))
speed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speed)


def test_aggregates_are_tile_based_and_weighted_separately():
    frame = pd.DataFrame({"avg_d_kbps": [1000, 3000, 9000], "tests": [1, 3, 0]})
    result = speed.summarize(frame)
    assert result["tile_count"] == 3
    assert result["median_mbps"] == 3
    assert result["test_weighted_mean_mbps"] == 2.5
    assert np.isclose(result["ideal_1gb_minutes"], 8000 / 3 / 60)


def test_empty_and_invalid_speed_are_not_treated_as_zero():
    frame = pd.DataFrame({"avg_d_kbps": [0, np.nan, -1], "tests": [1, 1, 1]})
    result = speed.summarize(frame)
    assert result["valid_speed_tiles"] == 0
    assert result["median_mbps"] is None
    assert result["ideal_1gb_minutes"] is None

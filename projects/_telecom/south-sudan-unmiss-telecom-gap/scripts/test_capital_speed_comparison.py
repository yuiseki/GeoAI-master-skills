import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("capital_speed", Path(__file__).with_name("06_capital_speed_comparison.py"))
capital = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capital)


def test_radius_selection_uses_geodesic_and_retains_boundary_center():
    df = pd.DataFrame({"lon": [0.0, 0.05, 0.2], "lat": [0.0, 0.0, 0.0]})
    mask = capital.within_radius(df, 0, 0, 10)
    assert np.array_equal(mask, [True, True, False])

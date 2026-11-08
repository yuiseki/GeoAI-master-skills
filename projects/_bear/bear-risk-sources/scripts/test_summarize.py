"""uvx --python 3.12 --with pandas --with pytest pytest -q -p no:cacheprovider test_summarize.py"""

# summarise of summarize.py and overlaps of fetch_overture.py.
import pandas as pd
import pytest

from fetch_overture import overlaps
from summarize import summarise


def test_summarise_means_and_paired_differences_from_base():
    df = pd.DataFrame([
        ("base", "akita", 1, "gifu", 0.30), ("base", "akita", 1, "iwate", 0.50), ("base", "akita+gifu", 2, "iwate", 0.40),
        ("clim", "akita", 1, "gifu", 0.35), ("clim", "akita", 1, "iwate", 0.45), ("clim", "akita+gifu", 2, "iwate", 0.60),
    ], columns=["variant", "train", "k", "target", "capture5"])
    mean, diff, wins, per_target = summarise(df)
    assert mean.loc["base", 1] == pytest.approx(0.40) and mean.loc["clim", 2] == pytest.approx(0.60)
    # clim - base on the same (train, target): +0.05, -0.05 (k = 1) and +0.20 (k = 2)
    assert diff.loc[("clim", 1), "mean"] == pytest.approx(0.0) and diff.loc[("clim", 1), "count"] == 2
    assert diff.loc[("clim", 1), "min"] == pytest.approx(-0.05) and diff.loc[("clim", 2), "max"] == pytest.approx(0.20)
    assert wins.to_dict() == {"clim": 2}
    assert per_target.loc["clim", "iwate"] == pytest.approx(0.525) and "base" not in diff.index.get_level_values(0)


def test_overlaps_of_bounding_boxes():
    a = (139.0, 39.0, 141.0, 41.0)
    assert overlaps(a, (140.0, 40.0, 142.0, 42.0)) and overlaps(a, (141.0, 41.0, 142.0, 42.0))   # touching corner
    assert not overlaps(a, (141.1, 39.0, 142.0, 41.0)) and not overlaps(a, (139.0, 41.5, 141.0, 42.0))

"""uv run --no-project --with pytest python3 -m pytest -q projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/test_plot.py"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from plot import map_share


def test_map_share_distinguishes_zero_from_missing():
    assert map_share({"stop_older_population": "0", "single_older_population": "0"}) is None
    assert map_share({"stop_older_population": "100", "single_older_population": "0"}) == 0
    assert map_share({"stop_older_population": "100", "single_older_population": "40"}) == 40
    with pytest.raises(ValueError):
        map_share({"stop_older_population": "100", "single_older_population": "101"})

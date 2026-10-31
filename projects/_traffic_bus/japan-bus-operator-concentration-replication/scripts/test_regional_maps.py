"""uv run --no-project --with pytest --with numpy --with scipy python3 -m pytest -q projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/test_regional_maps.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from regional_maps import REGIONS, pref_codes, top_by_count


def test_regions_cover_each_prefecture_once():
    codes = [c for region in REGIONS for c in pref_codes(region)]
    assert sorted(codes) == [f"{p:02d}" for p in range(1, 48)]


def test_top_by_count_ranks_people_not_share_and_skips_zero():
    rows = [
        {"code5": "01100", "single_older_population": "300"},
        {"code5": "01202", "single_older_population": "900"},
        {"code5": "01203", "single_older_population": "300"},
        {"code5": "01204", "single_older_population": "0"},
    ]
    assert [(k, r["code5"]) for k, r in top_by_count(rows, 5)] == [(1, "01202"), (2, "01100"), (3, "01203")]

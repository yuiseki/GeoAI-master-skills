"""uv run --no-project --with pytest python3 -m pytest -q projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/test_diagnostics.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from diagnostics import top_overlap, summarize_municipalities


def test_top_overlap_uses_same_ids_not_rank_positions():
    a = {"A": 3, "B": 2, "C": 1}
    b = {"A": 1, "B": 3, "C": 2}
    assert top_overlap(a, b, 2) == 1


def test_municipality_summary_excludes_zero_denominator():
    rows = [
        {"code5": "01", "name": "A", "stop_older_population": 10_000, "single_older_population": 10_000},
        {"code5": "02", "name": "B", "stop_older_population": 9_999, "single_older_population": 9_999},
        {"code5": "03", "name": "C", "stop_older_population": 0, "single_older_population": 0},
    ]
    assert summarize_municipalities(rows)["share_100pct_with_denominator_10000"] == 1

"""Tests for the rows the figures read (they come from the outputs unchanged)."""

import plot


def test_diff_rows_reads_the_confirmation():
    conf = {"targets": {"2025": {"retrospective": {"M5": {"diff_capture@5%": {"diff": 0.1, "lo90": -0.1, "hi90": 0.2}}}}}}
    assert plot.diff_rows(conf, 2025) == [("M5", 0.1, -0.1, 0.2)]

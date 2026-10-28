"""Tests for the rows the figures read (they come from the outputs unchanged)."""

import plot


def test_diff_rows_reads_the_confirmation():
    conf = {"targets": {"2025": {"retrospective": {"M5": {"diff_capture@5%": {"diff": 0.1, "lo90": -0.1, "hi90": 0.2}}}}}}
    assert plot.diff_rows(conf, 2025) == [("M5", 0.1, -0.1, 0.2)]


def test_crossfit_rows():
    import plot_crossfit

    x = {"targets": {"2025": {"retrospective": {"in_sample_original": {"fit": {"beta": -0.01, "se_beta": 0.02}},
                                                 "cross_fit": {"fit": {"beta": -0.07, "se_beta": 0.02},
                                                               "diff_capture@5%": {"diff": 0.0004, "lo90": -0.001, "hi90": 0.004}}}}}}
    assert plot_crossfit.rows(x) == [("2025", -0.01, 0.02, -0.07, 0.02, 0.0004, -0.001, 0.004)]

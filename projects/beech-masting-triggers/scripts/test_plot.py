"""Tests for the figure rows (they come from the block outputs unchanged)."""

import plot


def test_rmse_rows_pair_development_and_confirmation():
    b1 = {"loyo_rmse": {m: i / 10 for i, m in enumerate(plot.MODEL_LABELS)}}
    b2 = {"auxiliary": {"refit_on_dev": {m: {"rmse": 1 + i / 10} for i, m in enumerate(plot.MODEL_LABELS)}}}
    rows = plot.rmse_rows(b1, b2)
    assert rows[0] == ("M0", 0.0, 1.0) and rows[-1] == ("M7", 0.7, 1.7)


def test_cue_rows_mark_the_planned_tests():
    ci = {"spearman": 0.1, "ci90": [-0.1, 0.3]}
    b4 = {"Ts_lag1_vs_flowering": ci,
          "auxiliary_exploratory": {k: ci for k in ("Ts_lag1 vs F", "dT vs flower", "dT vs F", "F_lag vs flower",
                                                    "F_lag vs F", "Tsp vs loss")}}
    b5 = {"confirmatory": {k: {"spearman": 0.2, "ci95": [-0.2, 0.5]} for k in ("S1_t-1", "S2_t-1")},
          "auxiliary_exploratory": {"S3 vs loss": ci}}
    rows = plot.cue_rows(b4, b5)
    assert len(rows) == 10
    assert [r[4] for r in rows].count(True) == 3
    assert rows[7][1:4] == (0.2, -0.2, 0.5)

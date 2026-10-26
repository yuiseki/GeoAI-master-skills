import json

import numpy as np

import plot


def test_mae_values_are_read_from_the_scores_file_not_recomputed(tmp_path):
    scores = {"naive|h1": {"mae": 2.5}, "naive|h4": {"mae": 5.0}, "hgb|h1": {"mae": 2.75}, "hgb|h4": {"mae": 4.0}}
    p = tmp_path / "s.json"
    json.dump(scores, open(p, "w"))
    v = plot.mae_values(str(p), ["naive", "hgb"], [1, 4])
    assert v == {"naive": [2.5, 5.0], "hgb": [2.75, 4.0]}


def test_mae_values_stops_on_a_missing_model(tmp_path):
    p = tmp_path / "s.json"
    json.dump({"naive|h1": {"mae": 1.0}}, open(p, "w"))
    try:
        plot.mae_values(str(p), ["naive", "hgb"], [1])
        raise AssertionError("should stop")
    except KeyError:
        pass


def test_weekly_totals_sum_the_municipalities_per_week():
    import pandas as pd

    df = pd.DataFrame({"code5": ["a", "b", "a", "b"], "week_start": ["2022-04-11", "2022-04-11", "2022-04-18", "2022-04-18"], "bear": [1, 2, 3, 4]})
    s = plot.weekly_totals(df)
    assert list(s.values) == [3, 7]

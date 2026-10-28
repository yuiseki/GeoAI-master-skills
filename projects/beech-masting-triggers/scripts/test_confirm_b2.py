"""Known-answer tests for the confirmation helpers."""

import numpy as np
import pandas as pd
import pytest

import confirm_b2 as cf


def frame():
    return pd.DataFrame({"pref": ["A", "B"] * 3, "year": [1, 1, 2, 2, 3, 3],
                         "x": [1.0, 2.0, 10.0, 20.0, 100.0, 200.0], "F": [0.0, 1.0, 5.0, 7.0, 1.0, 3.0]})


def test_permute_years_moves_whole_years():
    df = frame()
    out = cf.permute_years(df, ["x"], np.random.default_rng(3))
    pairs = {tuple(out[out.year == y].x) for y in (1, 2, 3)}
    assert pairs == {(1.0, 2.0), (10.0, 20.0), (100.0, 200.0)}
    assert out.F.tolist() == df.F.tolist()


def test_within_year_slope_ignores_year_levels():
    df = frame()
    # deviations of x: (-0.5,0.5), (-5,5), (-50,50); of F: (-0.5,0.5), (-1,1), (-1,1)
    want = (0.25 + 5 + 50) / (0.25 + 25 + 2500)
    assert cf.within_year(df, "x") == pytest.approx(want)


def test_classes_follow_the_thresholds():
    assert cf.classes(np.array([0.9, 1.0, 1.9, 2.0, 3.4, 3.5])).tolist() == [0, 1, 1, 2, 2, 3]


def test_year_boot_spearman_of_a_perfect_relation_is_one():
    import stage_b4 as sb

    df = pd.DataFrame({"year": [1, 1, 2, 2, 3, 3], "x": [1, 2, 3, 4, 5, 6], "y": [2, 4, 6, 8, 10, 12]})
    assert sb.spearman(df.x, df.y) == pytest.approx(1)
    lo, hi = sb.year_boot_spearman(df, "x", "y", B=100)
    assert lo == pytest.approx(1) and hi == pytest.approx(1)

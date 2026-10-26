"""uvx --with numpy --with pandas --with pyarrow --with pytest pytest test_score_risk_map.py

Expected values are worked out by hand on a few cells, or by a brute force that repeats cells instead of weighting them.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import score_risk_map as sr

HERE = Path(__file__).parent


def test_a_perfect_map_captures_all_positives_that_fit_in_the_budget():
    pos = np.zeros(100, dtype=bool)
    pos[:3] = True
    assert sr.capture(sr.rank_order(pos.astype(float)), pos, 0.05) == 1.0
    pos[:10] = True  # 10 positives, a budget of 5 cells: at most half
    assert sr.capture(sr.rank_order(pos.astype(float)), pos, 0.05) == 0.5


def test_the_cell_straddling_the_cut_counts_by_its_fraction():
    pos = np.array([True, True] + [False] * 8)
    order = sr.rank_order(np.arange(10)[::-1].astype(float))
    assert np.isclose(sr.capture(order, pos, 0.15), (1 + 0.5) / 2)


def test_ties_go_by_the_second_key_then_at_random_and_average_to_the_budget():
    s = np.array([1.0, 1.0, 1.0, 0.0])
    assert list(sr.rank_order(s, np.array([0.0, 2.0, 1.0, 9.0]))[:3]) == [1, 2, 0]
    pos = np.zeros(1000, dtype=bool)
    pos[:100] = True  # a map with every cell tied: the positives first in the table must not be favoured
    caps = [sr.capture(sr.rank_order(np.zeros(1000), seed=k), pos, 0.05) for k in range(50)]
    assert abs(np.mean(caps) - 0.05) < 0.01


def test_counts_give_the_share_of_the_events_not_of_the_cells():
    order = sr.rank_order(np.array([4.0, 3, 2, 1]))
    assert np.isclose(sr.capture(order, np.array([5.0, 0, 1, 0]), 0.25), 5 / 6)


def test_weighted_capture_equals_repeating_the_cells():
    rng = np.random.default_rng(0)
    for trial in range(20):
        score = rng.random(60)
        pos = rng.random(60) < 0.3
        w = rng.integers(0, 4, size=60).astype(float)
        rep = np.repeat(np.arange(60), w.astype(int))
        a = sr.capture(sr.rank_order(score), pos, 0.1, weights=w)
        b = sr.capture(sr.rank_order(score[rep]), pos[rep], 0.1)
        assert np.isclose(a, b), trial


def test_block_interval_excludes_zero_for_a_clear_win_and_holds_zero_for_the_same_map():
    rng = np.random.default_rng(1)
    n = 4000
    blocks = np.repeat(np.arange(40), n // 40)
    pos = rng.random(n) < 0.05
    good = pos + rng.normal(0, 0.3, n)
    bad = rng.normal(0, 1, n)
    lo, hi = sr.bootstrap_diff(sr.rank_order(good), sr.rank_order(bad), pos, blocks, 0.05, B=200)
    assert lo > 0
    lo, hi = sr.bootstrap_diff(sr.rank_order(good), sr.rank_order(good), pos, blocks, 0.05, B=50)
    assert lo <= 0 <= hi


def test_coarsen_by_hand():
    ix, iy = np.array([0, 1, 2, 3]), np.array([0, 0, 0, 0])
    lab, s = sr.coarsen(ix, iy, np.array([0, 1, 0, 0]), np.array([0.1, 0.2, 0.5, 0.0]), 2, prob=True)
    assert list(lab) == [True, False] and np.allclose(s, [1 - 0.9 * 0.8, 0.5])
    _, s = sr.coarsen(ix, iy, np.zeros(4), np.array([2.0, 4.0, 9.0, 1.0]), 2, prob=False)
    assert np.allclose(s, [3.0, 5.0])


def test_command_line_end_to_end(tmp_path):
    rng = np.random.default_rng(2)
    n = 2000
    ix, iy = np.arange(n) % 50, np.arange(n) // 50
    label = (rng.random(n) < 0.04).astype(int)
    df = pd.DataFrame({"ix": ix, "iy": iy, "block": (ix // 10) * 100 + iy // 10, "y": label,
                       "good": label + rng.normal(0, 0.5, n), "noise": rng.random(n)})
    df.to_parquet(tmp_path / "t.parquet")
    out = tmp_path / "o.json"
    r = subprocess.run([sys.executable, str(HERE / "score_risk_map.py"), str(tmp_path / "t.parquet"), "--label", "y",
                        "--scores", "good", "noise", "--block", "block", "--compare", "good:noise", "--boot", "100",
                        "--grid", "ix", "iy", "--factors", "5", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    res = json.loads(out.read_text())
    assert res["maps"]["good"]["capture@0.05"] > res["maps"]["noise"]["capture@0.05"]
    assert res["compare"]["good - noise"]["lo90"] > 0
    assert res["coarser"]["5"]["oracle"] <= 1.0


def test_command_line_stops_on_a_missing_label(tmp_path):
    pd.DataFrame({"y": [1.0, None], "s": [0.1, 0.2]}).to_parquet(tmp_path / "t.parquet")
    r = subprocess.run([sys.executable, str(HERE / "score_risk_map.py"), str(tmp_path / "t.parquet"), "--label", "y",
                        "--scores", "s"], capture_output=True, text=True)
    assert r.returncode != 0 and "no label" in (r.stderr + r.stdout)

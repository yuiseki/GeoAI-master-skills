"""uvx --python 3.12 --with numpy --with scipy --with scikit-image --with pytest pytest -q -p no:cacheprovider test_quality_blocks.py"""

# Helpers of 03_quality.py (ENL from the log-ratio variance, block reduction) and 04_blocks.py (ENL rule, pixel sets,
# shares, simulated false alarm rate).
import importlib
import json
import math

import numpy as np
import pytest

qu = importlib.import_module("03_quality")
bk = importlib.import_module("04_blocks")


def test_l_from_logratio_var_inverts_two_trigamma():
    # trigamma(1) = pi^2 / 6, so var = pi^2 / 3 means L = 1; trigamma(4) = pi^2/6 - 1 - 1/4 - 1/9
    assert qu.l_from_logratio_var(math.pi ** 2 / 3) == pytest.approx(1.0, rel=1e-6)
    assert qu.l_from_logratio_var(2 * (math.pi ** 2 / 6 - 1 - 1 / 4 - 1 / 9)) == pytest.approx(4.0, rel=1e-6)
    assert math.isnan(qu.l_from_logratio_var(0.0)) and math.isnan(qu.l_from_logratio_var(float("nan")))


def test_l_from_logratio_var_matches_simulated_gamma_speckle():
    rng = np.random.default_rng(0)
    x, y = rng.gamma(5, 1 / 5, 400_000), rng.gamma(5, 1 / 5, 400_000)
    assert qu.l_from_logratio_var(np.var(np.log(x / y))) == pytest.approx(5, rel=0.03)


def test_block_reduce_keeps_only_full_blocks_and_drops_the_ragged_edge():
    m = np.ones((25, 32), bool)
    m[3, 15] = False                                    # spoils block (0, 1)
    b = qu.block_reduce(m, 10)
    assert b.shape == (2, 3)
    assert b.tolist() == [[True, False, True], [True, True, True]]


def test_share_counts_within_the_selection():
    mask = np.array([1, 1, 0, 0, 1], bool)
    sel = np.array([1, 1, 1, 0, 0], bool)
    assert bk.share(mask, sel) == {"n": 3, "k": 2, "share": 0.6667}
    assert bk.share(mask, np.zeros(5, bool)) == {"n": 0, "k": 0, "share": None}


def test_enl_rule_is_the_median_of_the_ratio_enl(tmp_path, monkeypatch):
    q = {"orbits": {"39": [{"enl_ratio_vv": 4.0, "enl_ratio_vh": 5.0}, {"enl_ratio_vv": 7.0}],
                    "141": [{"date": "x"}, {"enl_ratio_vh": 6.04}]}}
    (tmp_path / "quality.json").write_text(json.dumps(q), encoding="utf-8")
    monkeypatch.setattr(bk, "OUT", tmp_path)
    assert bk.enl_rule() == (5.5, 4)                   # median of [4, 5, 7, 6.04] = 5.52 -> 5.5


def test_pixel_sets():
    wc = np.full((60, 60), 30)
    wc[:, 50:] = 80                                     # water
    wc[40:, :20] = 10                                   # trees
    dem = np.full((60, 60), 5.0)
    dem[40:, :20] = 20.0
    ref = np.zeros((60, 60), bool)
    ref[:5, :5] = True                                  # 0924 outline
    ref2 = np.zeros((60, 60), bool)
    ref2[:3, :3] = True                                 # 1001 outline (smaller)
    aux = {"wc": wc, "dem": dem, "ref_0922": np.zeros_like(ref), "ref_0924": ref, "ref_0925": np.zeros_like(ref),
           "ref_1001": ref2}
    sets, edge = bk.pixel_sets(aux)
    assert sets["IN39"].sum() == 25 and sets["IN141"].sum() == 9 and sets["RECEDED"].sum() == 16
    # control: grassland, < 10 m, >= 300 m (30 pixels of 10 m) from the outline, not water
    assert sets["CTRL"][0, 35] and not sets["CTRL"][0, 33] and not sets["CTRL"][0, 55]
    assert not sets["CTRL"][45, 5] and sets["STABLE"][45, 5]
    # land-cover edge: a 5 x 5 window (2 pixels each side) that sees two classes
    assert edge[0, 48] and edge[0, 51] and not edge[0, 47] and not edge[0, 40]


def test_sim_false_alarm_is_near_alpha_for_two_dates():
    # With 2 dates the sequential omnibus test is a single two-sided test, so its false alarm rate is about alpha.
    assert bk.sim_false_alarm(2, 4.4, 0.01, 2, n=100_000) == pytest.approx(0.01, abs=0.003)

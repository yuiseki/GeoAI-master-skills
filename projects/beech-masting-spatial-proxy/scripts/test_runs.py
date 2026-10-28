import numpy as np
import pandas as pd
import pytest

import run_confirm as RC
import run_dev as RD


def test_choice_rule_and_ties():
    c = {(300, "w1"): {"M4": 1.0, "M5": 0.90}, (300, "w2"): {"M4": 1.0, "M5": 0.95},
         (1000, "w1"): {"M4": 0.95, "M5": 0.9005}, (1000, "w2"): {"M4": 1.0, "M5": 0.99}}
    # 0.9005 is within 0.001 of 0.90, so the tie goes to r = 1000 and w1; M5 is 0.0495 below M4 there
    assert RD.choose(c) == {"radius": 1000, "water": "w1", "g_star": "M5"}
    c[(1000, "w1")] = {"M4": 0.9008, "M5": 0.9005}
    assert RD.choose(c)["g_star"] == "M4"  # not 0.001 better: the simpler one


def test_morans_i_sign():
    sites = pd.DataFrame({"ID": range(1, 21), "x": np.r_[np.zeros(10), np.full(10, 1e5)] + np.arange(20),
                          "y_m": np.zeros(20)})
    clustered = pd.DataFrame({"ID": range(1, 21), "r": np.r_[np.ones(10), -np.ones(10)]})
    assert RC.morans_i(clustered, sites) == pytest.approx(1.0)
    alternating = pd.DataFrame({"ID": range(1, 21), "r": np.tile([1.0, -1.0], 10)})
    assert RC.morans_i(alternating, sites) < 0.2

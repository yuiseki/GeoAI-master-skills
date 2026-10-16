"""uvx --with numpy --with scipy --with pandas --with rdrobust --with pytest pytest test_rdd_crosscheck.py

sharp and fuzzy against rdrobust 2.1.1 with the same fixed bandwidth, local linear, triangular kernel and HC1
variance: the conventional estimate and its standard error. With GEOAI_REALDATA=1, the US Senate incumbency
data of the rdrobust examples (vote share at the next election against the margin of victory).
"""

import os

import numpy as np
import pytest
from rdrobust import rdrobust

from rdd import fuzzy, sharp


def _world(seed, n=3000):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    d = (rng.random(n) < 0.15 + 0.6 * (x >= 0)).astype(float)
    y = 1.5 * d + x + 0.5 * x ** 2 + rng.normal(size=n)
    ys = 1.0 * (x >= 0) + x + 0.5 * x ** 2 + rng.normal(size=n)
    return x, d, y, ys


def _ref(y, x, h, fuzzy_d=None):
    r = rdrobust(y, x, c=0, h=h, p=1, kernel="tri", vce="hc1", fuzzy=fuzzy_d)
    return float(r.coef.iloc[0, 0]), float(r.se.iloc[0, 0])


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("h", [0.3, 0.7])
def test_sharp_matches_rdrobust(seed, h):
    x, _, _, ys = _world(seed)
    tau, se = _ref(ys, x, h)
    ours = sharp(ys, x, 0.0, h)
    assert ours["tau"] == pytest.approx(tau, rel=1e-8)
    assert ours["se"] == pytest.approx(se, rel=1e-6)


@pytest.mark.parametrize("seed", range(3))
def test_fuzzy_matches_rdrobust(seed):
    x, d, y, _ = _world(seed)
    tau, se = _ref(y, x, 0.5, fuzzy_d=d)
    ours = fuzzy(y, d, x, 0.0, 0.5)
    assert ours["tau"] == pytest.approx(tau, rel=1e-8)
    assert ours["se"] == pytest.approx(se, rel=1e-6)


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_senate_incumbency():
    import pandas as pd

    d = pd.read_csv("https://raw.githubusercontent.com/rdpackages/rdrobust/master/Python/rdrobust_senate.csv")
    d = d.dropna(subset=["vote", "margin"])
    for h in (10.0, 17.75, 30.0):
        tau, se = _ref(d.vote.to_numpy(), d.margin.to_numpy(), h)
        ours = sharp(d.vote.to_numpy(), d.margin.to_numpy(), 0.0, h)
        assert ours["tau"] == pytest.approx(tau, rel=1e-8)
        print(h, ours)

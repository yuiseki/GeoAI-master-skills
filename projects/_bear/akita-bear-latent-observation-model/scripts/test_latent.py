"""Known-answer tests for the estimands, and a recovery test of the static shared model on synthetic data."""

import numpy as np
import pytest

import latent as lt
import simulate as sm
from test_simulate import TARGETS, fake


def test_estimands_read_the_mean_bear_change_the_reporting_change_and_the_tree_slope():
    muni = np.array([0, 0, 1, 1])
    z = np.array([-1.0, 1.0, -1.0, 1.0])
    d = np.zeros((1, 4, 4))
    d[0, 3] = [0.5, 0.1, 0.5, 0.1]
    a = np.array([[0.0, 0.0, 0.0, 0.2]])
    r = np.zeros((1, 4, 2))
    r[0, 3, 1] = 0.4
    e = lt.estimands({"d": d, "a": a, "r": r}, {"muni": muni, "z_tree": z})
    assert e["T_B"][0] == pytest.approx(0.3)
    assert e["T_R"][0] == pytest.approx(0.2 + 0.2)
    assert e["S_B"][0] == pytest.approx(-0.2)


def test_detect_needs_the_whole_90_percent_interval_on_one_side():
    assert lt.detect(np.linspace(0.1, 1, 101)) == 1
    assert lt.detect(np.linspace(-1, -0.1, 101)) == -1
    assert lt.detect(np.linspace(-0.2, 1, 101)) == 0


def test_the_static_shared_model_recovers_loadings_and_the_latent_surface():
    pytest.importorskip("numpyro")
    import numpyro

    numpyro.set_host_device_count(2)
    d = fake(M=300, G=5, seed=4)
    tr = sm.truth(d, "S5", 4, TARGETS)
    sim, _ = sm.simulate(d, tr, 4)
    s, diag = lt.fit(lt.model_shared, sim, seed=0, warmup=400, samples=400, use_H=True)
    assert diag["max_rhat"] < 1.05
    covered = sum(lt.interval(s[k])[0] <= sm.TRUE[k] <= lt.interval(s[k])[1] for k in ("lam_E", "lam_K", "c_E", "c_K"))
    assert covered >= 3
    assert np.corrcoef(s["b"].mean(0), tr["b"])[0, 1] > 0.7

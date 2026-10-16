"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pytest pytest test_cox.py"""

import numpy as np
import pytest

from cox import fit, k_function, k_lgcp, k_thomas, simulate_lgcp, simulate_thomas

W = (0.0, 1.0, 0.0, 1.0)
RS = np.linspace(0.01, 0.2, 20)


def test_k_by_hand_with_and_without_the_translation_weight():
    x, y = np.array([0.25, 0.75, 0.25]), np.array([0.5, 0.5, 0.25])
    # ordered pairs closer than 0.3: (0, 2) and (2, 0), offset (0, 0.25); |W| / (n (n - 1)) = 1 / 6
    assert k_function(x, y, W, [0.3], "none")[0] == pytest.approx(2 / 6)
    assert k_function(x, y, W, [0.3])[0] == pytest.approx(2 / 6 / 0.75)  # weight 1 / (1 * 0.75)


def test_k_of_a_poisson_pattern_is_pi_r_squared_only_with_the_edge_correction():
    ks, kn = [], []
    for s in range(50):
        rng = np.random.default_rng(s)
        n = rng.poisson(200)
        x, y = rng.random(n), rng.random(n)
        ks.append(k_function(x, y, W, RS))
        kn.append(k_function(x, y, W, RS, "none"))
    ratio = np.mean(ks, 0) / (np.pi * RS ** 2)
    assert np.abs(ratio[5:] - 1).max() < 0.03
    assert (np.mean(kn, 0) / (np.pi * RS ** 2))[-1] < 0.88  # measured 0.84 at r 0.2: pairs lost at the edge


def test_the_thomas_formula_matches_simulations():
    mean_k = np.mean([k_function(*simulate_thomas(25, 10, 0.03, W, seed=s), W, RS) for s in range(50)], 0)
    np.testing.assert_allclose(mean_k / k_thomas(RS, 25, 0.03), 1, atol=0.04)  # measured within 0.021


def test_the_lgcp_integral_matches_simulations():
    # The simulated field sits on a 40 x 40 grid, uniform within cells, and n is estimated from each pattern:
    # the mean K comes out 1-4% low (measured 0.958-0.989).
    mean_k = np.mean([k_function(*simulate_lgcp(np.log(200) - 0.5, 1.0, 0.08, W, seed=s), W, RS)
                      for s in range(30)], 0)
    np.testing.assert_allclose(mean_k / k_lgcp(RS, 1.0, 0.08), 0.97, atol=0.04)
    assert k_lgcp([0.1], 0.0, 0.08)[0] == pytest.approx(np.pi * 0.01)  # no variance: Poisson


def test_thomas_parameters_are_recovered():
    est = np.array([fit(RS, k_function(*p, W, RS), "thomas", 1.0, len(p[0]))["params"] for p in
                    (simulate_thomas(25, 10, 0.03, W, seed=100 + s) for s in range(8))])
    kappa, sigma = np.median(est, 0)
    assert kappa == pytest.approx(25, rel=0.3)
    assert sigma == pytest.approx(0.03, rel=0.25)


def test_lgcp_parameters_come_back_only_loosely_in_a_window_a_dozen_scales_wide():
    est = np.array([fit(RS, k_function(*p, W, RS), "lgcp", 1.0, len(p[0]))["params"] for p in
                    (simulate_lgcp(np.log(200) - 0.5, 1.0, 0.08, W, seed=s) for s in range(12))])
    var, scale = np.median(est, 0)
    assert var == pytest.approx(1.0, rel=0.3)
    assert scale == pytest.approx(0.08, rel=0.45)  # measured median 0.067 over 30 patterns, 10-90% 0.038-0.117


def _outside_envelope(f, L, nsim=19):
    sims = []
    for s in range(nsim):
        if f["model"] == "thomas":
            sx, sy = simulate_thomas(f["kappa"], f["mu"], f["sigma"], W, seed=500 + s)
        else:
            sx, sy = simulate_lgcp(f["mean_log"], f["var"], f["scale"], W, seed=500 + s)
        sims.append(np.sqrt(k_function(sx, sy, W, RS) / np.pi) - RS)
    sims = np.array(sims)
    return int(((L < sims.min(0)) | (L > sims.max(0))).sum())


def test_k_cannot_tell_attraction_from_an_unobserved_environment():
    # A Thomas pattern (offspring near parents) and an LGCP pattern (independent points in a random field): each
    # model fitted to each pattern puts the observed L(r) - r inside the envelope of 19 simulations. The true
    # model's contrast is lower (measured 0.0007 v 0.0035 and 0.00006 v 0.0005), but the envelopes cannot say so.
    for x, y in (simulate_thomas(25, 10, 0.03, W, seed=300), simulate_lgcp(np.log(200) - 0.5, 1.0, 0.08, W, seed=300)):
        kh = k_function(x, y, W, RS)
        L = np.sqrt(kh / np.pi) - RS
        for model in ("thomas", "lgcp"):
            assert _outside_envelope(fit(RS, kh, model, 1.0, len(x)), L) == 0


def test_a_trend_with_no_clustering_is_fitted_as_a_stationary_cluster_process():
    # Poisson points thinned by exp(3 (x - 1)): no interaction and no random field, only a west-east trend.
    rng = np.random.default_rng(301)
    n = rng.poisson(600)
    x, y = rng.random(n), rng.random(n)
    keep = rng.random(n) < np.exp(3 * (x - 1))
    kh = k_function(x[keep], y[keep], W, RS)
    f = fit(RS, kh, "thomas", 1.0, keep.sum())
    assert not f["at_edge"]
    assert _outside_envelope(f, np.sqrt(kh / np.pi) - RS) == 0

"""uvx --python 3.8 --with tick --with numpy --with scipy --with pytest pytest test_hawkes_crosscheck.py

The temporal part against tick (0.7, the last release; it installs only on Python 3.8 here). tick has no spatial
Hawkes, so the events are put at one point and the window's area made 2 pi sigma^2: the spatial kernel is then
1 / A at every event, and the space-time log-likelihood is the temporal one less n log A. The spatial kernel is
checked only against numerical integration (test_hawkes.py).

tick's loss for the exponential kernel is -(log-likelihood + T) / n.
"""

import numpy as np
import pytest
from scipy.optimize import minimize

from hawkes import fit, loglik, simulate

tick_hawkes = pytest.importorskip("tick.hawkes")

SIGMA = 1.0
SIDE = np.sqrt(2 * np.pi) * SIGMA
WINDOW = (0.0, SIDE, 0.0, SIDE)
T = 400.0


def _events():
    t = simulate(0.5, 0.5, 1.0, 1e-9, T, (0.0, 1e3, 0.0, 1e3), seed=3)["t"]
    return t, np.zeros(len(t)), np.zeros(len(t))


def _tick_loglik(model, mu, K):
    return -model.loss(np.array([mu, K])) * model.n_jumps - T


def test_log_likelihood_matches_tick():
    t, x, y = _events()
    for mu, K, beta in [(0.6, 0.4, 1.3), (0.2, 0.8, 0.5), (1.0, 0.05, 4.0)]:
        m = tick_hawkes.ModelHawkesExpKernLogLik(beta).fit([t], end_times=T)
        ours = loglik((mu, K, beta, SIGMA), t, x, y, T, WINDOW) + len(t) * np.log(SIDE * SIDE)
        assert ours == pytest.approx(_tick_loglik(m, mu, K), rel=1e-12)


def test_maximum_likelihood_matches_tick_at_the_fitted_decay():
    # tick fixes the decay; maximise its likelihood over (mu, K) at our beta, and check that other decays are worse.
    t, x, y = _events()
    mu, K, beta, sigma = fit(t, x, y, T, WINDOW, min_sigma=SIGMA)["params"]
    assert sigma == pytest.approx(SIGMA)
    best = {}
    for b in (beta, 0.7 * beta, 1.5 * beta):
        m = tick_hawkes.ModelHawkesExpKernLogLik(b).fit([t], end_times=T)
        r = minimize(m.loss, [0.3, 0.3], method="L-BFGS-B", bounds=[(1e-6, None), (0.0, 0.999)],
                     options={"ftol": 1e-14, "gtol": 1e-10})
        best[b] = (r.x, -r.fun * m.n_jumps - T)
    (tmu, tK), top = best[beta]
    assert tmu == pytest.approx(mu, rel=1e-5)
    assert tK == pytest.approx(K, rel=1e-5)
    assert all(v[1] < top for b, v in best.items() if b != beta)

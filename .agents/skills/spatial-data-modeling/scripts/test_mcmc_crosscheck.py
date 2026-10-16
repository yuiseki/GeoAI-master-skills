"""uvx --with numpy --with scipy --with arviz --with pytest pytest test_mcmc_crosscheck.py

rhat and ess_bulk against ArviZ 1.3.0 (az.rhat method="rank", az.ess method="bulk") on independent draws,
autocorrelated chains and chains that disagree.
"""

import arviz as az
import numpy as np
import pytest

from mcmc import ess_bulk, rhat


def _chains(kind, seed):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(4, 800))
    if kind == "ar":
        for t in range(1, 800):
            x[:, t] = 0.9 * x[:, t - 1] + x[:, t]
    if kind == "shifted":
        x += np.array([0, 0.2, 0.5, 1.0])[:, None]
    return x


@pytest.mark.parametrize("kind", ["iid", "ar", "shifted"])
@pytest.mark.parametrize("seed", range(3))
def test_diagnostics_match_arviz(kind, seed):
    x = _chains(kind, seed)
    assert rhat(x) == pytest.approx(float(az.rhat(x, method="rank")), rel=1e-8)
    assert ess_bulk(x) == pytest.approx(float(az.ess(x, method="bulk")), rel=1e-6)

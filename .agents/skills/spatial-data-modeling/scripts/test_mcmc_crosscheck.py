"""uvx --with numpy --with scipy --with arviz --with pymc --with geopandas --with libpysal --with pytest pytest test_mcmc_crosscheck.py

rhat and ess_bulk against ArviZ 1.3.0 (az.rhat method="rank", az.ess method="bulk") on independent draws,
autocorrelated chains and chains that disagree. The BYM2 model's HMC against the same model in PyMC 6.3.2
(NUTS): posterior medians of alpha, sigma and rho within four combined Monte Carlo standard errors, and the area
effects' means. GEOAI_REALDATA=1 also runs Scotlip (libpysal's example data, downloaded).
"""

import os

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


def _bym2_pymc(y, E, nb, draws=1000, tune=2000, seed=1):
    """The same BYM2 model in PyMC (NUTS): an ICAR potential per component with a soft sum to zero, N(0, 1)
    for units alone, the same priors and scaling."""
    pm = pytest.importorskip("pymc")
    import pytensor.tensor as pt

    from mcmc import bym2_scaling, neighbour_components

    n = len(y)
    lab = neighbour_components(nb)
    sc = bym2_scaling(nb, lab)
    alone = np.nonzero([len(v) == 0 for v in nb])[0]
    I, J = zip(*[(i, j) for i, v in enumerate(nb) for j in v if i < j])
    comps = [np.nonzero(lab == k)[0] for k in np.unique(lab) if (lab == k).sum() > 1]
    with pm.Model():
        a = pm.Normal("a", 0, 10)
        sig = pm.HalfNormal("sig", 1)
        rho = pm.Beta("rho", 0.5, 0.5)
        th = pm.Normal("th", 0, 1, shape=n)
        ph = pm.Flat("ph", shape=n)
        pot = -0.5 * pt.sum((ph[list(I)] - ph[list(J)]) ** 2)
        if len(alone):
            pot = pot - 0.5 * pt.sum(ph[alone] ** 2)
        for c in comps:
            pot = pot - 0.5 * pt.sum(ph[c]) ** 2 / (0.001 * len(c)) ** 2
        pm.Potential("icar", pot)
        b = pm.Deterministic("b", sig * (pt.sqrt(1 - rho) * th + pt.sqrt(rho / sc) * ph))
        pm.Poisson("y", mu=E * pt.exp(a + b), observed=y)
        return pm.sample(draws, tune=tune, chains=4, cores=1, target_accept=0.9, random_seed=seed,
                         progressbar=False).posterior


def _agree(ours, theirs):
    from mcmc import ess_bulk

    se = np.sqrt(ours.var() / ess_bulk(ours) + theirs.var() / ess_bulk(theirs))
    return abs(np.median(ours) - np.median(theirs)) < 4 * se + 1e-3


def _grid_world():
    side = 5
    nb = []
    for i in range(side * side):
        r, c = divmod(i, side)
        nb.append(np.array([j for j in (i - side, i + side, i - 1 if c else -1, i + 1 if c < side - 1 else -1)
                            if 0 <= j < side * side]))
    nb.append(np.array([], int))  # an island
    rng = np.random.default_rng(7)
    E = rng.uniform(5, 20, 26)
    u = np.r_[np.linspace(-0.6, 0.6, 25), 0.3]
    return rng.poisson(E * np.exp(u)), E, nb


def test_bym2_hmc_matches_pymc_nuts_on_a_small_grid_with_an_island():
    from mcmc import poisson_bym2

    y, E, nb = _grid_world()
    ours = poisson_bym2(y, E, nb, draws=1000, warmup=2000, chains=4, seed=0)
    post = _bym2_pymc(y, E, nb)
    for k, kk in (("alpha", "a"), ("sigma", "sig"), ("rho", "rho")):
        assert _agree(ours[k], post[kk].values), k
    b_ours, b_theirs = ours["b"].reshape(-1, 26).mean(0), post["b"].values.reshape(-1, 26).mean(0)
    assert np.abs(b_ours - b_theirs).max() < 0.25 * ours["b"].reshape(-1, 26).std(0).mean()


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_bym2_on_scotlip_matches_pymc():
    gpd = pytest.importorskip("geopandas")
    libpysal = pytest.importorskip("libpysal")
    from mcmc import poisson_bym2

    g = gpd.read_file(libpysal.examples.load_example("Scotlip").get_path("scotlip.shp"))
    w = libpysal.weights.Queen.from_dataframe(g, use_index=False, silence_warnings=True)
    nb = [np.array(sorted(w.neighbors[i]), int) for i in range(len(g))]
    y, E = g.CANCER.to_numpy(int), g.CEXP.to_numpy(float)
    ours = poisson_bym2(y, E, nb, draws=1000, warmup=2000, chains=4, seed=0)
    post = _bym2_pymc(y, E, nb)
    for k, kk in (("alpha", "a"), ("sigma", "sig"), ("rho", "rho")):
        assert _agree(ours[k], post[kk].values), k

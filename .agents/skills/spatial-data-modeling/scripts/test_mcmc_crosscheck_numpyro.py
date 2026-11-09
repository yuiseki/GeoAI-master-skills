"""uvx --with numpy --with scipy --with arviz --with numpyro==0.22.0 --with geopandas --with libpysal --with pytest pytest test_mcmc_crosscheck_numpyro.py

The BYM2 model's HMC (mcmc.py) against the same model in NumPyro (NUTS on JAX), a second outside implementation
beside PyMC (test_mcmc_crosscheck.py). What differs from ours: the sampler, the gradients (JAX's autodiff, not our
hand-written ones) and the change of variables for sigma > 0 and 0 < rho < 1 (NumPyro adds the Jacobians itself).
What does not: the ICAR potential and the scaling factor are written the same way, so this does not check them
(the ring by hand in test_mcmc.py does).

JAX runs on the CPU only: on a machine whose GPU is shared, JAX would otherwise take 75% of its memory at import.
GEOAI_REALDATA=1 also runs Scotlip (libpysal's example data, downloaded).
"""

import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import numpy as np
import pytest

from test_mcmc_crosscheck import _agree, _grid_world


def _bym2_numpyro(y, E, nb, draws=1000, warmup=2000, seed=1):
    """The model of _bym2_pymc: an ICAR potential per component with a soft sum to zero, N(0, 1) for units alone,
    a ~ N(0, 10), sigma ~ HalfNormal(1), rho ~ Beta(0.5, 0.5), the same scaling."""
    numpyro = pytest.importorskip("numpyro")
    import jax
    import jax.numpy as jnp
    import numpyro.distributions as dist
    from numpyro.infer import MCMC, NUTS

    from mcmc import bym2_scaling, neighbour_components

    numpyro.set_host_device_count(4)
    n = len(y)
    lab = neighbour_components(nb)
    sc = jnp.asarray(bym2_scaling(nb, lab))            # one factor per area (1 for units alone)
    alone = np.nonzero([len(v) == 0 for v in nb])[0]
    I, J = (np.array(x) for x in zip(*[(i, j) for i, v in enumerate(nb) for j in v if i < j]))
    comps = [np.nonzero(lab == k)[0] for k in np.unique(lab) if (lab == k).sum() > 1]

    def model():
        a = numpyro.sample("a", dist.Normal(0, 10))
        sig = numpyro.sample("sig", dist.HalfNormal(1))
        rho = numpyro.sample("rho", dist.Beta(0.5, 0.5))
        th = numpyro.sample("th", dist.Normal(0, 1).expand([n]).to_event(1))
        ph = numpyro.sample("ph", dist.ImproperUniform(dist.constraints.real_vector, (), (n,)))
        pot = -0.5 * jnp.sum((ph[I] - ph[J]) ** 2)
        if len(alone):
            pot = pot - 0.5 * jnp.sum(ph[alone] ** 2)
        for c in comps:
            pot = pot - 0.5 * jnp.sum(ph[c]) ** 2 / (0.001 * len(c)) ** 2
        numpyro.factor("icar", pot)
        b = numpyro.deterministic("b", sig * (jnp.sqrt(1 - rho) * th + jnp.sqrt(rho / sc) * ph))
        numpyro.sample("y", dist.Poisson(E * jnp.exp(a + b)), obs=y)

    m = MCMC(NUTS(model, target_accept_prob=0.9), num_warmup=warmup, num_samples=draws, num_chains=4,
             chain_method="sequential", progress_bar=False)
    m.run(jax.random.PRNGKey(seed))
    return {k: np.asarray(v) for k, v in m.get_samples(group_by_chain=True).items()}


def test_bym2_hmc_matches_numpyro_nuts_on_a_small_grid_with_an_island():
    from mcmc import poisson_bym2

    y, E, nb = _grid_world()
    ours = poisson_bym2(y, E, nb, draws=1000, warmup=2000, chains=4, seed=0)
    post = _bym2_numpyro(y, E, nb)
    for k, kk in (("alpha", "a"), ("sigma", "sig"), ("rho", "rho")):
        assert _agree(ours[k], post[kk]), k
    b_ours, b_theirs = ours["b"].reshape(-1, 26).mean(0), post["b"].reshape(-1, 26).mean(0)
    assert np.abs(b_ours - b_theirs).max() < 0.25 * ours["b"].reshape(-1, 26).std(0).mean()


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_bym2_on_scotlip_matches_numpyro():
    gpd = pytest.importorskip("geopandas")
    libpysal = pytest.importorskip("libpysal")
    from mcmc import ess_bulk, poisson_bym2, rhat

    g = gpd.read_file(libpysal.examples.load_example("Scotlip").get_path("scotlip.shp"))
    w = libpysal.weights.Queen.from_dataframe(g, use_index=False, silence_warnings=True)
    nb = [np.array(sorted(w.neighbors[i]), int) for i in range(len(g))]
    y, E = g.CANCER.to_numpy(int), g.CEXP.to_numpy(float)
    ours = poisson_bym2(y, E, nb, draws=1000, warmup=2000, chains=4, seed=0)
    post = _bym2_numpyro(y, E, nb)
    for k, kk in (("alpha", "a"), ("sigma", "sig"), ("rho", "rho")):
        x = post[kk]
        print(f"{k}: ours {np.median(ours[k]):.3f} ({ours[k].std():.3f}) numpyro {np.median(x):.3f} ({x.std():.3f})"
              f" rhat {rhat(x):.3f} ess {ess_bulk(x):.0f}")
        assert _agree(ours[k], x), k
    bo, bt = ours["b"].reshape(-1, len(g)).mean(0), post["b"].reshape(-1, len(g)).mean(0)
    print(f"b: max diff {np.abs(bo - bt).max():.3f} corr {np.corrcoef(bo, bt)[0, 1]:.4f}")

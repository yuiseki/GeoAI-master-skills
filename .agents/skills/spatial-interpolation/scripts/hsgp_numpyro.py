"""HSGP with its parameters inferred: NumPyro (NUTS on JAX), the basis of hsgp.py.

    v_i = a + f(x_i) + e_i,  f = Phi (sqrt(S(sqrt(lambda))) * beta),  beta ~ N(0, 1),  e ~ N(0, noise^2)

a ~ N(mean v, 2 sd v), sigma ~ HalfNormal(sd v), noise ~ HalfNormal(sd v), ell ~ LogNormal(log(S / 2), 1) with S
the half range of the points. Use coordinates in km (or a unit where the half range is around 1 to 100).

After the fit, check the paper's diagnostic: the length scale must exceed the shortest one that m and c can
represent (`ell_min`); if not, raise m and c from the estimate and fit again. In two dimensions the rule's m is
too few for the posterior sd (hsgp.py, test_hsgp.py): fit again with 1.5 to 2 times m and see that the
predictions and their sd stay.

JAX takes 75% of a GPU's memory when it loads: JAX_PLATFORMS=cpu is set here unless the caller set it.
"""

import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import numpy as np

from hsgp import _NU, _RULE, basis, sqrt_eigenvalues


def _spd(w, kind, sigma, ell):
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    if kind == "se":
        return sigma ** 2 * 2 * jnp.pi * ell ** 2 * jnp.exp(-0.5 * (ell * w) ** 2)
    nu = _NU[kind]
    logc = 2 * jnp.log(2.0) + jnp.log(jnp.pi) + gammaln(nu + 1) + nu * jnp.log(2 * nu) - gammaln(nu) - 2 * nu * jnp.log(ell)
    return sigma ** 2 * jnp.exp(logc) * (2 * nu / ell ** 2 + w ** 2) ** -(nu + 1)


def model(phi, sw, v, kind, half):
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist
    mv, sv = float(np.mean(v)), float(np.std(v))
    a = numpyro.sample("a", dist.Normal(mv, 2 * sv))
    sigma = numpyro.sample("sigma", dist.HalfNormal(sv))
    ell = numpyro.sample("ell", dist.LogNormal(np.log(half / 2), 1.0))
    noise = numpyro.sample("noise", dist.HalfNormal(sv))
    beta = numpyro.sample("beta", dist.Normal(0, 1).expand([phi.shape[1]]).to_event(1))
    f = phi @ (jnp.sqrt(_spd(sw, kind, sigma, ell)) * beta)
    numpyro.sample("v", dist.Normal(a + f, noise), obs=v)


def fit(xy, v, box, m, kind="matern52", draws=1000, warmup=1000, chains=4, seed=0, target_accept=0.9):
    import jax
    import numpyro
    from numpyro.infer import MCMC, NUTS
    numpyro.set_host_device_count(chains)
    phi = basis(xy - box.center, box.L, m)
    sw = sqrt_eigenvalues(box.L, m)
    mc = MCMC(NUTS(model, target_accept_prob=target_accept), num_warmup=warmup, num_samples=draws,
              num_chains=chains, chain_method="sequential", progress_bar=False)
    mc.run(jax.random.PRNGKey(seed), phi, sw, np.asarray(v, float), kind, float(box.half.max()))
    out = {k: np.asarray(x) for k, x in mc.get_samples(group_by_chain=True).items()}
    out["diverging"] = int(np.asarray(mc.get_extra_fields()["diverging"]).sum())
    return out


def predict(post, q, box, m, kind="matern52", seed=0):
    """Draws of the latent surface at q (draws, len(q)) and of a new observation there (with the noise)."""
    import jax.numpy as jnp
    if not box.inside(q).all():
        raise ValueError("prediction points outside the box: widen it (c) to cover them")
    pq = basis(q - box.center, box.L, m)
    sw = sqrt_eigenvalues(box.L, m)
    a, s, e, n = (post[k].reshape(-1) for k in ("a", "sigma", "ell", "noise"))
    beta = post["beta"].reshape(len(a), -1)
    w = np.asarray(jnp.sqrt(_spd(sw[None, :], kind, s[:, None], e[:, None]))) * beta
    f = a[:, None] + w @ pq.T
    rng = np.random.default_rng(seed)
    return f, f + rng.normal(size=f.shape) * n[:, None]


def ell_min(kind, c, m, half):
    """The shortest length scale that m basis functions per axis and the factor c represent (paper eq. 18-22)."""
    return _RULE[kind][0] * c * half / m

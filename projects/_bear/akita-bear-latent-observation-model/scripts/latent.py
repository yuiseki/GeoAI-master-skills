"""The latent-state models (EXPERIMENT_PLAN.md) in NumPyro, the fitting with diagnostics, and the estimands.

Data dict (arrays over the M core meshes): XB [M, 5] standardised bear-side prior covariates, H [M] human-side PC1,
muni [M] municipality index 0..G-1, offset [M] log cell count, E [2, M] Ministry records (E6, E7), Y [4, M]
April-September report counts (2023-2026), env_mask [2, M] and y_mask [4, M] (False = hidden), and optional extras
for the value-of-information runs. Nothing here reads files.
"""

import numpy as np

YEARS = (2023, 2024, 2025, 2026)
PRIORS = {
    "default": {"a": 2.5, "g": 0.5, "sv": 0.5, "sr": 0.5, "su": 1.0},
    "wide": {"a": 5.0, "g": 1.5, "sv": 1.5, "sr": 1.5, "su": 3.0},
}


def _np():
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist

    return jnp, numpyro, dist


def _reporting(numpyro, dist, jnp, G, pr, extras):
    """Year effects a_y and municipality x year effects r[y, g]; with V5 history, indicator effects instead."""
    if extras and "history" in extras:
        a0 = numpyro.sample("a0", dist.Normal(0, pr["a"]))
        bz = numpyro.sample("beta_hist", dist.Normal(0, 1).expand([extras["history"]["Z"].shape[0]]))
        sr = numpyro.sample("sr", dist.HalfNormal(pr["sr"]))
        rg = numpyro.sample("rg", dist.Normal(0, 1).expand([G])) * sr
        eff = a0 + jnp.einsum("k,kyg->yg", bz, extras["history"]["Z"]) + rg[None, :]
        numpyro.deterministic("a", jnp.full(len(YEARS), a0))
        numpyro.deterministic("r", eff - a0)
        return eff
    a = numpyro.sample("a", dist.Normal(0, pr["a"]).expand([len(YEARS)]))
    sr = numpyro.sample("sr", dist.HalfNormal(pr["sr"]))
    r = numpyro.deterministic("r", numpyro.sample("r_raw", dist.Normal(0, 1).expand([len(YEARS), G])) * sr)
    return a[:, None] + r


def model_independent(data, use_H=False, prior="default"):
    """L0 / L0H: each source with its own covariate effects and its own mesh effect; nothing shared."""
    jnp, numpyro, dist = _np()
    pr = PRIORS[prior]
    M, G = data["XB"].shape[0], int(data["G"])
    K = data["XB"].shape[1]
    bE = numpyro.sample("beta_E", dist.Normal(0, 1).expand([K]))
    sE = numpyro.sample("s_E", dist.HalfNormal(pr["su"]))
    uE = numpyro.sample("u_E", dist.Normal(0, 1).expand([M])) * sE
    aE = numpyro.sample("a_E", dist.Normal(0, pr["a"]).expand([2]))
    lin_E = aE[:, None] + (data["XB"] @ bE + uE)[None, :]
    bK = numpyro.sample("beta_K", dist.Normal(0, 1).expand([K]))
    sK = numpyro.sample("s_K", dist.HalfNormal(pr["su"]))
    uK = numpyro.sample("u_K", dist.Normal(0, 1).expand([M])) * sK
    rep = _reporting(numpyro, dist, jnp, G, pr, None)
    lin_K = data["offset"][None, :] + rep[:, data["muni"]] + (data["XB"] @ bK + uK)[None, :]
    if use_H:
        lin_E = lin_E + numpyro.sample("c_E", dist.Normal(0, 1)) * data["H"][None, :]
        lin_K = lin_K + numpyro.sample("c_K", dist.Normal(0, 1)) * data["H"][None, :]
    _likelihoods(numpyro, dist, jnp, data, lin_E, lin_K)


def model_shared(data, use_H=False, interaction=False, dynamic=False, prior="default", extras=None):
    """L1 (shared static b), L2 (+H), the B x H variant, and L3 (dynamic d[m, y] in the Kumadas years)."""
    jnp, numpyro, dist = _np()
    pr = PRIORS[prior]
    M, G = data["XB"].shape[0], int(data["G"])
    K = data["XB"].shape[1]
    beta = numpyro.sample("beta", dist.Normal(0, 1).expand([K]))
    u = numpyro.sample("u", dist.Normal(0, 1).expand([M]))
    b = numpyro.deterministic("b", data["XB"] @ beta + u)
    lE = numpyro.sample("lam_E", dist.HalfNormal(1.0))
    lK = numpyro.sample("lam_K", dist.HalfNormal(1.0))
    aE = numpyro.sample("a_E", dist.Normal(0, pr["a"]).expand([2]))
    H = data["H"]
    Hy = extras["H_obs"] if extras and "H_obs" in extras else jnp.broadcast_to(H, (len(YEARS), M))
    if dynamic:
        g = numpyro.sample("g", dist.Normal(0, pr["g"]).expand([len(YEARS) - 1]))
        sv = numpyro.sample("sv", dist.HalfNormal(pr["sv"]))
        v = numpyro.sample("v", dist.Normal(0, 1).expand([len(YEARS) - 1, M]))
        d = numpyro.deterministic("d", jnp.concatenate([jnp.zeros((1, M)), g[:, None] + sv * v], 0))
    else:
        d = jnp.zeros((len(YEARS), M))
    By = b[None, :] + d
    rep = _reporting(numpyro, dist, jnp, G, pr, extras)
    lin_E = aE[:, None] + lE * b[None, :]
    lin_K = data["offset"][None, :] + rep[:, data["muni"]] + lK * By
    cE = cK = 0.0
    if use_H:
        cE = numpyro.sample("c_E", dist.Normal(0, 1))
        cK = numpyro.sample("c_K", dist.Normal(0, 1))
        lin_E = lin_E + cE * H[None, :]
        lin_K = lin_K + cK * Hy
    if interaction:
        lin_K = lin_K + numpyro.sample("kappa", dist.Normal(0, 0.5)) * By * Hy
    _likelihoods(numpyro, dist, jnp, data, lin_E, lin_K)
    if extras:
        _extra_likelihoods(numpyro, dist, jnp, data, extras, By, b, lE, cE, H)


def _likelihoods(numpyro, dist, jnp, data, lin_E, lin_K):
    phi = numpyro.sample("phi", dist.HalfNormal(5.0))
    with numpyro.handlers.mask(mask=data["env_mask"]):
        numpyro.sample("obs_E", dist.Bernoulli(logits=lin_E), obs=data["E"])
    with numpyro.handlers.mask(mask=data["y_mask"]):
        numpyro.sample("obs_Y", dist.NegativeBinomial2(jnp.exp(lin_K), phi), obs=data["Y"])


def _extra_likelihoods(numpyro, dist, jnp, data, extras, By, b, lE, cE, H):
    if "camera" in extras:  # V1 / V2: detection days at sites, known effort
        c = extras["camera"]
        a_cam = numpyro.sample("a_cam", dist.Normal(0, 2.5))
        l_cam = numpyro.sample("lam_cam", dist.HalfNormal(1.0))
        rate = jnp.exp(jnp.log(c["effort"]) + a_cam + l_cam * By[c["year"], c["mesh"]])
        numpyro.sample("obs_cam", dist.Poisson(rate), obs=c["days"])
    if "capture" in extras:  # V3: captures per municipality x year, known effort
        c = extras["capture"]
        a_cap = numpyro.sample("a_cap", dist.Normal(0, 2.5))
        l_cap = numpyro.sample("lam_cap", dist.HalfNormal(1.0))
        mB = By @ c["W"].T  # [Y, G] municipality means of B
        numpyro.sample("obs_cap", dist.Poisson(jnp.exp(jnp.log(c["effort"]) + a_cap + l_cap * mB)), obs=c["count"])
    if "env2020s" in extras:  # V4: Ministry-style survey in 2023 and 2026, one detection intercept for both
        c = extras["env2020s"]
        a8 = numpyro.sample("a_E8", dist.Normal(0, 2.5))
        lin = a8 + lE * By[jnp.array([0, 3])] + cE * H[None, :]
        numpyro.sample("obs_E8", dist.Bernoulli(logits=lin), obs=c["E8"])


def fit(model, data, seed=0, chains=2, warmup=500, samples=500, dense=None, **kw):
    """NUTS; returns (samples dict, diagnostics dict). dense: sites given a dense mass matrix block."""
    import jax
    from numpyro.diagnostics import summary
    from numpyro.infer import MCMC, NUTS

    kernel = NUTS(model, dense_mass=[tuple(dense)] if dense else False)
    mcmc = MCMC(kernel, num_warmup=warmup, num_samples=samples, num_chains=chains,
                chain_method="parallel", progress_bar=False)
    mcmc.run(jax.random.PRNGKey(seed), data, extra_fields=("diverging",), **kw)
    grouped = mcmc.get_samples(group_by_chain=True)
    stats = summary({k: v for k, v in grouped.items() if not k.startswith("obs")})
    rhat = max(float(np.nanmax(s["r_hat"])) for s in stats.values())
    ess = min(float(np.nanmin(s["n_eff"])) for s in stats.values())
    div = float(np.mean(np.asarray(mcmc.get_extra_fields()["diverging"])))
    return {k: np.asarray(v) for k, v in mcmc.get_samples().items()}, {"max_rhat": rhat, "min_ess": ess, "divergent_share": div}


def estimands(s, data):
    """T_B, T_R and S_B per posterior draw (from a dynamic fit)."""
    d26 = s["d"][:, 3, :]
    T_B = d26.mean(1)
    r = s["r"]
    T_R = (s["a"][:, 3] - s["a"][:, 0]) + (r[:, 3, :] - r[:, 0, :])[:, data["muni"]].mean(1)
    z = data["z_tree"] - data["z_tree"].mean()
    S_B = ((d26 - d26.mean(1, keepdims=True)) * z[None, :]).sum(1) / (z ** 2).sum()
    return {"T_B": T_B, "T_R": T_R, "S_B": S_B}


def interval(x, level=0.90):
    lo, hi = np.quantile(x, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def detect(x):
    """+1 / -1 when the 90% interval excludes 0 on that side, 0 otherwise."""
    lo, hi = interval(x)
    return 1 if lo > 0 else (-1 if hi < 0 else 0)

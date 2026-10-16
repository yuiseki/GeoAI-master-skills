"""Markov chain Monte Carlo for small models, with the chain diagnostics that say whether to trust it.

    sample                  random-walk Metropolis on an unconstrained parameter vector: several chains from
                            dispersed starts, the proposal scale tuned during warm-up towards an acceptance of
                            about 0.3 (then fixed), warm-up discarded. The log density must include the
                            log-Jacobian of any transform (a rate sampled on its log needs + log rate)
    rhat                    rank-normalised split R-hat (Vehtari and others 2021): the larger of the bulk and the
                            folded (tail) versions. Near 1 when the chains agree
    ess_bulk                bulk effective sample size of the rank-normalised split chains (Geyer's initial
                            monotone sequence)
    poisson_random_intercepts  y ~ Poisson(exp(alpha + u[area]) * exposure), u ~ N(0, sigma^2),
                            alpha ~ N(0, 10^2), sigma ~ half-normal(1): a non-conjugate model, sampled on
                            (alpha, log sigma, u)

    hmc                     Hamiltonian Monte Carlo from a log density and its gradient: a jittered trajectory
                            length, the step size by dual averaging, a diagonal mass matrix from warm-up
    poisson_bym2            BYM2 disease mapping, y ~ Poisson(E exp(alpha + b)), b = sigma (sqrt(1 - rho) theta +
                            sqrt(rho / s) phi), phi an ICAR per connected component, units alone N(0, 1)

Random-walk Metropolis is slow in many dimensions and with correlated posteriors; the diagnostics show it
(R-hat above 1.01, small ESS). Use hmc there.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python mcmc.py TABLE COUNT AREA [--exposure COL]
        [--draws 2000] [--warmup 2000] [--chains 4]
"""

import argparse

import numpy as np
from scipy import stats


def sample(logp, x0, draws=2000, warmup=1000, chains=4, seed=0, scale=None):
    x0 = np.asarray(x0, float)
    d = len(x0)
    rng = np.random.default_rng(seed)
    out = np.empty((chains, draws, d))
    accepted = np.zeros(chains)
    for c in range(chains):
        x = x0 + rng.normal(scale=1.0, size=d)  # dispersed starts
        lp = logp(x)
        s = np.full(d, 0.5 if scale is None else scale) / np.sqrt(d)
        for t in range(warmup + draws):
            prop = x + s * rng.normal(size=d)
            lpp = logp(prop)
            ok = np.log(rng.random()) < lpp - lp
            if ok:
                x, lp = prop, lpp
            if t < warmup:  # Robbins-Monro towards an acceptance of 0.3
                s *= np.exp((float(ok) - 0.3) / (1 + t) ** 0.6)
            else:
                out[c, t - warmup] = x
                accepted[c] += ok
    return {"draws": out, "acceptance": accepted / draws}


def hmc(logp_grad, x0, draws=1000, warmup=1000, chains=4, seed=0, target=0.8, path=1.5, max_steps=256):
    """Hamiltonian Monte Carlo with a jittered trajectory length. logp_grad(x) returns (log density, gradient).

    Warm-up: the step size by dual averaging towards an acceptance of `target` (Hoffman and Gelman 2014); after
    the first half, the diagonal mass matrix is set to the draws' variances and the step size is tuned again.
    Each trajectory is about `path` (in units of the posterior sd) long, with its number of leapfrog steps drawn
    uniformly up to twice that over the step size. Divergences (an energy error above 1000) are counted."""
    x0 = np.asarray(x0, float)
    d = len(x0)
    rng = np.random.default_rng(seed)
    out = np.empty((chains, draws, d))
    stats_ = {"acceptance": np.zeros(chains), "divergent": np.zeros(chains, int), "step": np.zeros(chains),
              "steps_mean": np.zeros(chains)}

    def leapfrog(x, r, g, eps, inv_m, n):
        r = r + 0.5 * eps * g
        for k in range(n):
            x = x + eps * inv_m * r
            with np.errstate(over="ignore", invalid="ignore"):
                lp, g = logp_grad(x)
            if not np.isfinite(lp) or not np.all(np.isfinite(g)):
                return x, r, g, -np.inf
            r = r + (eps if k < n - 1 else 0.5 * eps) * g
        return x, r, g, lp

    for c in range(chains):
        x = x0 + rng.normal(scale=1.0, size=d)
        lp, g = logp_grad(x)
        inv_m = np.ones(d)
        eps, hist = 0.1, []

        def reset(e):
            return {"mu": np.log(10 * e), "hbar": 0.0, "logbar": 0.0, "t": 0}

        da = reset(eps)
        n_steps = []
        for t in range(warmup + draws):
            n = int(rng.integers(1, max(2, min(max_steps, int(2 * path / eps)) + 1)))
            r0 = rng.normal(size=d) / np.sqrt(inv_m)
            h0 = -lp + 0.5 * (r0 * r0 * inv_m).sum()
            xn, rn, gn, lpn = leapfrog(x, r0, g, eps, inv_m, n)
            h1 = -lpn + 0.5 * (rn * rn * inv_m).sum() if np.isfinite(lpn) else np.inf
            acc = float(np.exp(min(0.0, h0 - h1))) if np.isfinite(h1) else 0.0
            if h1 - h0 > 1000:
                if t >= warmup:
                    stats_["divergent"][c] += 1
            if rng.random() < acc:
                x, lp, g = xn, lpn, gn
            if t < warmup:
                da["t"] += 1
                m = da["t"]
                da["hbar"] = (1 - 1 / (m + 10)) * da["hbar"] + (target - acc) / (m + 10)
                log_eps = da["mu"] - np.sqrt(m) / 0.05 * da["hbar"]
                w = m ** -0.75
                da["logbar"] = w * log_eps + (1 - w) * da["logbar"]
                eps = float(np.exp(log_eps))
                if not np.isfinite(eps) or eps <= 0:
                    eps = 1e-3
                if t >= warmup // 4:
                    hist.append(x.copy())
                if t == warmup // 2 and len(hist) > 10:
                    inv_m = np.var(np.array(hist), axis=0) + 1e-6
                    da = reset(eps)
                if t == warmup - 1:
                    eps = float(np.exp(da["logbar"]))
            else:
                out[c, t - warmup] = x
                stats_["acceptance"][c] += acc
                n_steps.append(n)
        stats_["acceptance"][c] /= draws
        stats_["step"][c] = eps
        stats_["steps_mean"][c] = np.mean(n_steps)
    return {"draws": out, **stats_}


def neighbour_components(nb):
    """Connected components of a neighbour list (list of index arrays). Returns a component label per unit."""
    n = len(nb)
    lab = -np.ones(n, int)
    k = 0
    for s in range(n):
        if lab[s] >= 0:
            continue
        stack = [s]
        lab[s] = k
        while stack:
            i = stack.pop()
            for j in nb[i]:
                if lab[j] < 0:
                    lab[j] = k
                    stack.append(j)
        k += 1
    return lab


def bym2_scaling(nb, lab):
    """Per unit, the BYM2 scaling of its component (Riebler et al. 2016; Freni-Sterrantino et al. 2018 for
    disconnected graphs): the geometric mean of the marginal variances of the component's ICAR (generalised
    inverse of D - W). Units alone in their component get 1."""
    s = np.ones(len(nb))
    for k in np.unique(lab):
        idx = np.nonzero(lab == k)[0]
        if len(idx) < 2:
            continue
        pos = {u: i for i, u in enumerate(idx)}
        Q = np.zeros((len(idx), len(idx)))
        for u in idx:
            for v in nb[u]:
                Q[pos[u], pos[v]] = -1.0
            Q[pos[u], pos[u]] = len(nb[u])
        # the generalised inverse of a connected graph's Laplacian: (Q + 11'/m)^-1 - 11'/m (np.linalg.pinv's
        # default cut-off keeps the zero eigenvalue's rounding error and returns huge negative values)
        m = len(idx)
        G = np.linalg.inv(Q + np.ones((m, m)) / m) - np.ones((m, m)) / m
        s[idx] = np.exp(np.mean(np.log(np.diag(G))))
    return s


def bym2_logp_grad(nb, y, expected, prior_sd=10.0):
    """log density and gradient of y_i ~ Poisson(E_i exp(alpha + b_i)), b = sigma (sqrt(1 - rho) theta +
    sqrt(rho / s) phi), theta ~ N(0, I), phi an ICAR within each connected component (a soft sum to zero, sd
    0.001 x the component's size) and N(0, 1) for units alone. Priors alpha ~ N(0, prior_sd^2), sigma ~
    half-normal(1), rho ~ Beta(0.5, 0.5). Parameters: (alpha, log sigma, logit rho, theta (n), phi (n)), with
    the log-Jacobians of the two transforms."""
    y, E = np.asarray(y, float), np.asarray(expected, float)
    n = len(y)
    lab = neighbour_components(nb)
    sc = bym2_scaling(nb, lab)
    alone = np.array([len(nb[i]) == 0 for i in range(n)])
    deg = np.array([len(v) for v in nb], float)
    I, J = [], []
    for i, v in enumerate(nb):
        for j in v:
            if i < j:
                I.append(i)
                J.append(j)
    I, J = np.array(I, int), np.array(J, int)
    comps = [np.nonzero(lab == k)[0] for k in np.unique(lab) if (lab == k).sum() > 1]
    logE = np.log(E)

    def f(x):
        a, ls, lr = x[0], x[1], x[2]
        th, ph = x[3:3 + n], x[3 + n:]
        if not (abs(lr) < 30 and abs(ls) < 30):  # far outside any sensible value: reject
            return -np.inf, np.zeros_like(x)
        sig, rho = np.exp(ls), 1 / (1 + np.exp(-lr))
        log_rho, log_1mrho = -np.log1p(np.exp(-lr)), -np.log1p(np.exp(lr))
        u = np.sqrt(1 - rho) * th + np.sqrt(rho / sc) * ph
        eta = a + sig * u + logE
        mu = np.exp(eta)
        diff = ph[I] - ph[J]
        lp = (y * eta - mu).sum() - 0.5 * (a / prior_sd) ** 2 - 0.5 * sig ** 2 + ls  # half-normal + Jacobian
        lp += 0.5 * log_rho + 0.5 * log_1mrho  # Beta(0.5, 0.5) density and the logit's Jacobian
        lp += -0.5 * (th ** 2).sum() - 0.5 * (diff ** 2).sum() - 0.5 * (ph[alone] ** 2).sum()
        gph = np.zeros(n)
        np.add.at(gph, I, -diff)
        np.add.at(gph, J, diff)
        gph[alone] -= ph[alone]
        for idx in comps:
            tot = ph[idx].sum()
            v = (0.001 * len(idx)) ** 2
            lp -= 0.5 * tot ** 2 / v
            gph[idx] -= tot / v
        res = y - mu  # d loglik / d eta
        g = np.empty_like(x)
        g[0] = res.sum() - a / prior_sd ** 2
        g[1] = (res * sig * u).sum() - sig ** 2 + 1
        du_drho = -th / (2 * np.sqrt(1 - rho)) + ph / (2 * np.sqrt(rho * sc))
        g[2] = (res * sig * du_drho).sum() * rho * (1 - rho) + 0.5 - rho
        g[3:3 + n] = res * sig * np.sqrt(1 - rho) - th
        g[3 + n:] = res * sig * np.sqrt(rho / sc) + gph
        return float(lp), g

    return f, {"components": int(lab.max() + 1), "alone": int(alone.sum()), "scaling": sc}


def poisson_bym2(y, expected, nb, draws=1000, warmup=1000, chains=4, seed=0):
    f, info = bym2_logp_grad(nb, y, expected)
    n = len(y)
    a0 = float(np.clip(np.log((np.sum(y) + 0.5) / np.sum(expected)), -10, 10))
    x0 = np.r_[a0, np.log(0.5), 0.0, np.zeros(2 * n)]
    r = hmc(f, x0, draws, warmup, chains, seed)
    d = r["draws"]
    rho = 1 / (1 + np.exp(-d[:, :, 2]))
    sig = np.exp(d[:, :, 1])
    sc = info["scaling"]
    b = sig[..., None] * (np.sqrt(1 - rho)[..., None] * d[:, :, 3:3 + n] + np.sqrt(rho[..., None] / sc) * d[:, :, 3 + n:])
    return {"alpha": d[:, :, 0], "sigma": sig, "rho": rho, "b": b, "info": info,
            **{k: r[k] for k in ("acceptance", "divergent", "step", "steps_mean")}}


def _split(x):
    x = np.asarray(x, float)
    h = x.shape[1] // 2
    return np.vstack([x[:, :h], x[:, x.shape[1] - h:]])


def _z(x):
    r = stats.rankdata(x, method="average").reshape(x.shape)
    return stats.norm.ppf((r - 3 / 8) / (x.size + 1 / 4))  # Blom, as Stan and ArviZ


def _rhat_basic(x):
    n = x.shape[1]
    between = n * x.mean(1).var(ddof=1)
    within = x.var(1, ddof=1).mean()
    return float(np.sqrt((between / within + n - 1) / n))


def rhat(x):
    s = _split(x)
    bulk = _rhat_basic(_z(s))
    tail = _rhat_basic(_z(np.abs(s - np.median(s))))
    return max(bulk, tail)


def _autocov(x):
    n = x.shape[1]
    m = 1 << int(np.ceil(np.log2(2 * n)))
    f = np.fft.rfft(x - x.mean(1, keepdims=True), n=m, axis=1)
    return np.fft.irfft(f * np.conj(f), n=m, axis=1)[:, :n] / n


def _ess(x):
    chains, n = x.shape
    acov = _autocov(x)
    mean_var = acov[:, 0].mean() * n / (n - 1)
    var_plus = mean_var * (n - 1) / n + (x.mean(1).var(ddof=1) if chains > 1 else 0)
    rho = np.zeros(n)
    even, odd = 1.0, 1.0 - (mean_var - acov[:, 1].mean()) / var_plus
    rho[0], rho[1] = even, odd
    t = 1
    while t < n - 3 and even + odd > 0:
        even = 1.0 - (mean_var - acov[:, t + 1].mean()) / var_plus
        odd = 1.0 - (mean_var - acov[:, t + 2].mean()) / var_plus
        if even + odd >= 0:
            rho[t + 1], rho[t + 2] = even, odd
        t += 2
    max_t = t - 2
    if even > 0:
        rho[max_t + 1] = even
    t = 1
    while t <= max_t - 2:
        if rho[t + 1] + rho[t + 2] > rho[t - 1] + rho[t]:
            rho[t + 1] = rho[t + 2] = (rho[t - 1] + rho[t]) / 2
        t += 2
    total = chains * n
    tau = -1 + 2 * rho[:max_t + 1].sum() + rho[max_t + 1:max_t + 2].sum()
    tau = max(tau, 1 / np.log10(total))
    return float(total / tau)


def ess_bulk(x):
    return _ess(_z(_split(x)))


def poisson_random_intercepts(y, area, exposure=None, draws=2000, warmup=2000, chains=4, seed=0):
    y = np.asarray(y, float)
    codes, area = np.unique(np.asarray(area), return_inverse=True)
    J = len(codes)
    off = np.zeros(len(y)) if exposure is None else np.log(np.asarray(exposure, float))

    def logp(th):
        alpha, log_s, u = th[0], th[1], th[2:]
        s = np.exp(log_s)
        eta = alpha + u[area] + off
        return (float((y * eta - np.exp(eta)).sum())
                + stats.norm.logpdf(alpha, 0, 10) + stats.halfnorm.logpdf(s) + log_s
                + stats.norm.logpdf(u, 0, s).sum())

    x0 = np.r_[np.log(y.mean() + 0.5), 0.0, np.zeros(J)]
    r = sample(logp, x0, draws, warmup, chains, seed, scale=0.5)
    d = r["draws"]
    return {"alpha": d[:, :, 0], "sigma": np.exp(d[:, :, 1]), "u": d[:, :, 2:], "areas": codes,
            "acceptance": r["acceptance"]}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("count")
    p.add_argument("area")
    p.add_argument("--exposure")
    p.add_argument("--draws", type=int, default=2000)
    p.add_argument("--warmup", type=int, default=2000)
    p.add_argument("--chains", type=int, default=4)
    a = p.parse_args()

    import duckdb

    cols = [a.count, a.area] + ([a.exposure] if a.exposure else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("missing values in the columns used")
    y = np.array([r[0] for r in rows], float)
    area = np.array([str(r[1]) for r in rows])
    ex = np.array([r[2] for r in rows], float) if a.exposure else None
    r = poisson_random_intercepts(y, area, ex, a.draws, a.warmup, a.chains)
    print(f"rows {len(y)}, areas {len(r['areas'])}; acceptance by chain {np.round(r['acceptance'], 2).tolist()}")
    worst = []
    for name, d in (("alpha", r["alpha"]), ("sigma", r["sigma"])):
        q = np.quantile(d, [0.05, 0.5, 0.95])
        print(f"{name}: median {q[1]:.4g}, 90% interval {q[0]:.4g} to {q[2]:.4g}, R-hat {rhat(d):.3f}, "
              f"bulk ESS {ess_bulk(d):.0f}")
    for j in range(len(r["areas"])):
        worst.append((rhat(r["u"][:, :, j]), ess_bulk(r["u"][:, :, j])))
    print(f"area effects: worst R-hat {max(w[0] for w in worst):.3f}, smallest bulk ESS {min(w[1] for w in worst):.0f}; "
          "trust nothing with R-hat above 1.01")


if __name__ == "__main__":
    main()

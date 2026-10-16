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

Random-walk Metropolis is slow in many dimensions and with correlated posteriors; the diagnostics show it
(R-hat above 1.01, small ESS). It is meant for small models whose answer can be checked, not as a general
sampler.

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

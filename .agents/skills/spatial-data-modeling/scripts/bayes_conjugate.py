"""Bayesian updating in models that have a closed form: prior -> likelihood -> posterior -> posterior predictive,
with the prior predictive, posterior predictive checks and repeated-simulation diagnostics. No MCMC; the
closed forms here are the values a sampler for the same model must reproduce (use them as regression tests).

    beta_binomial      rate p with prior Beta(a, b), k successes in n: posterior Beta(a + k, b + n - k)
    beta_interval      equal-tailed credible interval of a Beta (regularised incomplete beta, bisection)
    beta_binomial_predictive  probability of j successes in m future trials (parameter uncertainty included)
    normal_normal      mean mu with prior N(m0, v0), n observations with known variance s2 and mean ybar:
                       posterior precision 1/v0 + n/s2, mean the precision-weighted average of m0 and ybar.
                       The weight on the data, (n/s2) / (1/v0 + n/s2) = v0 / (v0 + s2/n), is the partial
                       pooling weight of a multilevel model with group variance v0.
    normal_predictive  a new observation: mean the posterior mean, variance posterior variance + s2
                       (parameter uncertainty + the spread of a single observation)
    linear_gaussian    y = X beta + e, prior beta ~ N(m0, V0), e ~ N(0, s2): posterior N(m, V). Shows weak
                       identification: with y depending on a + b only, var(a) stays near v0/2 for any n.
    gamma_poisson      rate per unit exposure with prior Gamma(a, b) (shape, rate), counts y_i over exposures
                       e_i: posterior Gamma(a + sum y, b + sum e)
    gamma_poisson_predictive  mean and variance of the count over exposure E (negative binomial)
    simulate_prior_predictive  counts the prior alone would generate: check them before seeing the data
    ppc                posterior predictive p-value P(T(replicated) >= T(observed)) for a statistic T
    coverage_normal    share of credible intervals that contain the true mean over repeated worlds: a
                       diagnostic of the model and prior as a description of the generating process, not a
                       property a credible interval must have

A 95% credible interval says: under this model and this prior, the parameter lies in the interval with
posterior probability 0.95. A 95% confidence interval says: the procedure, repeated, covers the true value
95% of the time. They coincide only in special cases.

Usage:
    uvx --with numpy python bayes_conjugate.py rate K N --prior A B [--future M]
    uvx --with numpy python bayes_conjugate.py mean YBAR N S2 --prior M0 V0
"""

import argparse
import math

import numpy as np


def _check_proper(a, b, what):
    if a <= 0 or b <= 0:
        raise ValueError(f"{what} Beta({a}, {b}) is improper: a and b must be positive (an improper prior "
                         "needs data that make the posterior proper, and then still is not a probability)")


def beta_binomial(k, n, a=1.0, b=1.0):
    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and n")
    pa, pb = a + k, b + n - k
    _check_proper(pa, pb, "posterior")
    return {"a": pa, "b": pb, "mean": pa / (pa + pb),
            "var": pa * pb / ((pa + pb) ** 2 * (pa + pb + 1))}


def _betacf(a, b, x, iters=300, eps=1e-15):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, iters + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1) < eps:
            break
    return h


def beta_cdf(x, a, b):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def beta_quantile(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if beta_cdf(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def beta_interval(a, b, level=0.95):
    tail = (1 - level) / 2
    return beta_quantile(tail, a, b), beta_quantile(1 - tail, a, b)


def _lbeta(a, b):
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def beta_binomial_predictive(m, a, b):
    return [math.comb(m, j) * math.exp(_lbeta(a + j, b + m - j) - _lbeta(a, b)) for j in range(m + 1)]


def normal_normal(m0, v0, ybar, s2, n):
    prec = 1 / v0 + n / s2
    w = (n / s2) / prec
    return {"mean": (m0 / v0 + n * ybar / s2) / prec, "var": 1 / prec, "weight_on_data": w}


def normal_predictive(post_mean, post_var, s2):
    return {"mean": post_mean, "var": post_var + s2}


def linear_gaussian(X, y, m0, V0, s2):
    X, y = np.asarray(X, float), np.asarray(y, float)
    P0 = np.linalg.inv(np.asarray(V0, float))
    V = np.linalg.inv(P0 + X.T @ X / s2)
    m = V @ (P0 @ np.asarray(m0, float) + X.T @ y / s2)
    return {"mean": m, "cov": V}


def gamma_poisson(counts, exposures, a, b):
    if a <= 0 or b <= 0:
        raise ValueError(f"Gamma({a}, {b}) prior is improper")
    pa, pb = a + float(np.sum(counts)), b + float(np.sum(exposures))
    return {"a": pa, "b": pb, "mean": pa / pb, "var": pa / pb ** 2}


def gamma_poisson_predictive(a, b, exposure):
    mean = exposure * a / b
    return {"mean": mean, "var": mean + exposure ** 2 * a / b ** 2}


def simulate_prior_predictive(a, b, exposure, rng, draws=10000):
    rate = rng.gamma(a, 1 / b, draws)
    return rng.poisson(rate * exposure)


def ppc(observed, replicate, stat, rng, draws=2000):
    """replicate(rng) -> one replicated data set drawn with a fresh posterior parameter."""
    t_obs = stat(observed)
    t_rep = np.array([stat(replicate(rng)) for _ in range(draws)])
    return {"observed": float(t_obs), "replicated_mean": float(t_rep.mean()), "p": float(np.mean(t_rep >= t_obs))}


def coverage_normal(true_mu, m0, v0, s2, n, rng, reps=2000, level=0.95):
    z = {0.95: 1.959963984540054, 0.9: 1.6448536269514722}[level]
    hit, bias = 0, 0.0
    for _ in range(reps):
        ybar = rng.normal(true_mu, math.sqrt(s2 / n))
        p = normal_normal(m0, v0, ybar, s2, n)
        half = z * math.sqrt(p["var"])
        hit += abs(p["mean"] - true_mu) <= half
        bias += p["mean"] - true_mu
    return {"coverage": hit / reps, "bias": bias / reps}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rate")
    r.add_argument("k", type=int)
    r.add_argument("n", type=int)
    r.add_argument("--prior", type=float, nargs=2, default=[1, 1], metavar=("A", "B"))
    r.add_argument("--future", type=int, default=0)
    m = sub.add_parser("mean")
    for name in ("ybar", "n", "s2"):
        m.add_argument(name, type=float)
    m.add_argument("--prior", type=float, nargs=2, required=True, metavar=("M0", "V0"))
    a = p.parse_args()
    if a.cmd == "rate":
        post = beta_binomial(a.k, a.n, *a.prior)
        lo, hi = beta_interval(post["a"], post["b"])
        print(f"prior Beta({a.prior[0]:g}, {a.prior[1]:g}) mean {a.prior[0] / sum(a.prior):.4g}; "
              f"data {a.k}/{a.n} = {a.k / a.n:.4g}")
        print(f"posterior Beta({post['a']:g}, {post['b']:g}): mean {post['mean']:.4g}, sd {math.sqrt(post['var']):.4g}, "
              f"95% credible interval {lo:.4g} to {hi:.4g}")
        if a.future:
            pred = beta_binomial_predictive(a.future, post["a"], post["b"])
            mean = sum(j * q for j, q in enumerate(pred))
            print(f"next {a.future} trials: expected {mean:.4g} successes; P(0) {pred[0]:.4g}")
    else:
        post = normal_normal(a.prior[0], a.prior[1], a.ybar, a.s2, a.n)
        pred = normal_predictive(post["mean"], post["var"], a.s2)
        print(f"posterior mean {post['mean']:.4g}, variance {post['var']:.4g} (weight on the data "
              f"{post['weight_on_data']:.3f}); a new observation: mean {pred['mean']:.4g}, variance {pred['var']:.4g}")


if __name__ == "__main__":
    main()

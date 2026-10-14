"""Sample size from a target precision: how many sites to plan for, step by step.

The steps, each printed so that the assumption behind it can be read:
    n0        from the spread and the margin (half-width of the confidence interval) under simple random
              sampling: (z sd / margin)^2 for a mean, z^2 p (1 - p) / margin^2 for a proportion
    deff      multiplied by the design effect. A cluster design with m sites per cluster and intra-cluster
              correlation icc has deff = 1 + (m - 1) icc; the effective sample size is n / deff
    population  the finite population correction n / (1 + (n - 1) / N), when the frame holds N sites
    response  divided by the share of planned sites expected to be measured (access refused, flooded)

The spread is an input, not something this script knows: take it from a pilot sample (raised to an upper
confidence limit with pilot_sd_upper, because a small pilot often underestimates it), an earlier survey, or
a stated guess. There is no closed form here for spatial autocorrelation: a design whose sites are close
together gains less than its n suggests, and a spatially balanced design can gain more. Estimate the design
effect for a planned layout by simulation on a pilot or a plausible field (see references/sample-size.md).

Usage:
    uvx --with scipy python sample_size.py mean --sd 10 --margin 2 [--confidence 0.95] [--deff 1.9] \\
        [--population 5000] [--response 0.8] [--pilot-n 10 --pilot-level 0.8]
    uvx --with scipy python sample_size.py proportion --margin 0.05 [--p 0.5] [...]
"""

import argparse
import math

from scipy.stats import chi2, norm


def _z(confidence):
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    return float(norm.ppf(0.5 + confidence / 2))


def _positive(**kw):
    for k, v in kw.items():
        if not v > 0:
            raise ValueError(f"{k} must be positive")


def n_mean(sd, margin, confidence=0.95):
    _positive(sd=sd, margin=margin)
    return (_z(confidence) * sd / margin) ** 2


def margin_of_mean(sd, n, confidence=0.95):
    _positive(sd=sd, n=n)
    return _z(confidence) * sd / math.sqrt(n)


def n_proportion(margin, p=0.5, confidence=0.95):
    _positive(margin=margin)
    if not 0 <= p <= 1:
        raise ValueError("p must be between 0 and 1")
    return _z(confidence) ** 2 * p * (1 - p) / margin**2


def n_stratified(weights, sds, margin, confidence=0.95, allocation="proportional"):
    """Total n for the mean over strata with population shares `weights` and within-stratum sds; returns
    the total and the n of each stratum (proportional to W, or to W x S under Neyman allocation)."""
    _positive(margin=margin)
    if abs(sum(weights) - 1) > 1e-9:
        raise ValueError("stratum weights must add up to 1")
    z2 = _z(confidence) ** 2
    if allocation == "proportional":
        total = z2 * sum(w * s * s for w, s in zip(weights, sds)) / margin**2
        share = list(weights)
    elif allocation == "neyman":
        ws = [w * s for w, s in zip(weights, sds)]
        total = z2 * sum(ws) ** 2 / margin**2
        share = [x / sum(ws) for x in ws]
    else:
        raise ValueError("allocation is proportional or neyman")
    return total, [total * x for x in share]


def design_effect(cluster_size, icc):
    return 1 + (cluster_size - 1) * icc


def effective_n(n, deff):
    return n / deff


def pilot_sd_upper(sd, n, level=0.8):
    """One-sided upper confidence limit of the sd from a pilot of n sites."""
    if n < 2:
        raise ValueError("a pilot needs at least 2 sites")
    return sd * math.sqrt((n - 1) / chi2.ppf(1 - level, n - 1))


def plan(n0, deff=1.0, population=None, response=1.0):
    _positive(n0=n0, deff=deff)
    if not 0 < response <= 1:
        raise ValueError("response must be in (0, 1]")
    r = {"n0": n0, "after_deff": n0 * deff}
    n = r["after_deff"]
    if population:
        n = n / (1 + (n - 1) / population)
    r["after_population"] = n
    r["after_response"] = n / response
    r["n"] = math.ceil(r["after_response"] - 1e-9)
    r["expected_measured"] = r["n"] * response
    return r


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("target", choices=("mean", "proportion"))
    p.add_argument("--margin", type=float, required=True, help="half-width of the confidence interval")
    p.add_argument("--sd", type=float, help="standard deviation (mean)")
    p.add_argument("--p", type=float, default=0.5, help="expected proportion; 0.5 is the largest n")
    p.add_argument("--confidence", type=float, default=0.95)
    p.add_argument("--deff", type=float, default=1.0)
    p.add_argument("--population", type=int)
    p.add_argument("--response", type=float, default=1.0)
    p.add_argument("--pilot-n", type=int, help="the sd came from a pilot of this many sites")
    p.add_argument("--pilot-level", type=float, default=0.8)
    a = p.parse_args()
    if a.target == "mean":
        if a.sd is None:
            raise SystemExit("--sd is required for a mean")
        sd = a.sd
        if a.pilot_n:
            sd = pilot_sd_upper(a.sd, a.pilot_n, a.pilot_level)
            print(f"pilot sd {a.sd:g} from {a.pilot_n} sites -> {a.pilot_level:.0%} upper limit {sd:.3f}")
        n0 = n_mean(sd, a.margin, a.confidence)
    else:
        n0 = n_proportion(a.margin, a.p, a.confidence)
    r = plan(n0, a.deff, a.population, a.response)
    print(f"n0 (simple random sampling) {r['n0']:.1f}")
    print(f"x design effect {a.deff:g} -> {r['after_deff']:.1f}")
    if a.population:
        print(f"finite population N = {a.population} -> {r['after_population']:.1f}")
    print(f"/ expected response {a.response:g} -> {r['after_response']:.1f}")
    print(f"plan {r['n']} sites; about {r['expected_measured']:.0f} expected to be measured")


if __name__ == "__main__":
    main()

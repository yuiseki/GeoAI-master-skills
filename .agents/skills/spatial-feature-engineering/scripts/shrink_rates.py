"""Shrink rates with small denominators towards the overall rate (empirical Bayes, beta-binomial).

A rate from a few events (1 hotel among 5 POIs = 20%) swings by chance. Each unit's rate x / n is
replaced by (x + a) / (n + a + b), where a / (a + b) is the overall rate and a + b, the prior
strength, is estimated by the method of moments from how much the raw rates vary beyond what
binomial chance alone would make. Units with large n keep their rate; units with small n move
towards the overall rate. If the rates vary no more than chance, every unit gets the overall rate.

Usage:
    uvx --with numpy --with duckdb --with pyarrow python shrink_rates.py TABLE ID COUNT DENOMINATOR \
        [--out rates.parquet] [--top 10]
"""

import argparse

import numpy as np


def shrink(x, n):
    x, n = np.asarray(x, float), np.asarray(n, float)
    if (x < 0).any() or (x > n).any():
        raise SystemExit("counts must lie between 0 and their denominator")
    has = n > 0
    p = x[has].sum() / n[has].sum()
    raw = np.full(len(x), np.nan)
    raw[has] = x[has] / n[has]
    # Variance of the raw rates, weighted by n, minus the average binomial variance p(1-p)/n.
    w = n[has] / n[has].sum()
    observed = float(np.sum(w * (raw[has] - p) ** 2))
    chance = float(np.sum(w * p * (1 - p) / n[has]))
    between = observed - chance
    if between <= 0 or p in (0.0, 1.0):
        strength = np.inf
        shrunk = np.full(len(x), p)
    else:
        strength = p * (1 - p) / between - 1
        if strength <= 0:
            strength = 0.0
        a, b = p * strength, (1 - p) * strength
        shrunk = (x + a) / (n + a + b)
    return {"raw": raw, "shrunk": shrunk, "overall": p, "prior_strength": strength,
            "between_variance": between}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("count")
    p.add_argument("denominator")
    p.add_argument("--out")
    p.add_argument("--top", type=int, default=10)
    a = p.parse_args()

    import duckdb

    t = duckdb.sql(f'select "{a.id}", "{a.count}", "{a.denominator}" from \'{a.table}\'').fetchall()
    ids = [r[0] for r in t]
    x = np.array([r[1] for r in t], float)
    n = np.array([r[2] for r in t], float)
    r = shrink(x, n)
    print(f"units {len(ids)} ({int((n == 0).sum())} with no denominator), overall rate {r['overall']:.4g}, "
          f"prior strength a+b {r['prior_strength']:.4g} (a unit needs about this many to keep half "
          "its own rate)")
    order = np.argsort(-np.nan_to_num(np.abs(r["raw"] - r["shrunk"]), nan=0))
    print(f"largest moves (id: count / denominator, raw -> shrunk):")
    for i in order[:a.top]:
        print(f"  {ids[i]}: {x[i]:g} / {n[i]:g}, {r['raw'][i]:.3f} -> {r['shrunk'][i]:.3f}")
    if a.out:
        import pyarrow as pa

        out = pa.table({"id": [str(i) for i in ids], "count": x, "denominator": n,
                        "raw_rate": r["raw"], "shrunk_rate": r["shrunk"]})
        duckdb.sql(f"copy (select * from out) to '{a.out}' (format parquet)")


if __name__ == "__main__":
    main()

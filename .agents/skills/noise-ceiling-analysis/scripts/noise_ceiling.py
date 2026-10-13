"""Estimate the highest R2 any model could reach on a target, from what is known about its noise.

    repeat    two independent measurements of the same units (another period, another survey).
              With independent noise of equal size in both, the ceiling for predicting one of
              them is their correlation r: the share of its variance that is the stable signal.
              Predicting it by the other measurement gives only r squared, because that
              predictor is noisy too. A linear fit absorbs an overall shift between the two.
              With --halves, the two columns are halves of the target (first and second half of
              each period) and the target is their total: its ceiling is 2r / (1 + r)
              (Spearman-Brown). Splitting is the way to get two measurements for counts of
              events that come in bursts, where the Poisson ceiling below is far too high.
    counts    event counts. Under Poisson noise the variance is the variance of the rates plus
              their mean, so the ceiling is 1 - mean / variance (with --exposure, the expected
              Poisson variance is the mean count, and the rate is per unit of exposure).
    rounding  a value rounded to a step: the rounding error is uniform with variance step^2 / 12.

Usage:
    uvx --with duckdb --with numpy python noise_ceiling.py repeat TABLE COL1 COL2 [--halves] [--weight COL --bands 1 10 30]
    uvx --with duckdb --with numpy python noise_ceiling.py counts TABLE COUNT [--exposure COL] [--by COL]
    uvx --with duckdb --with numpy python noise_ceiling.py rounding TABLE COL --step 5
"""

import argparse

import numpy as np


def repeat_ceiling(y1, y2, halves_of_target=False):
    """Ceiling R2 from two measurements. With halves_of_target, y1 and y2 are the two halves of
    the target (events in the first and second half of each year) and the target is their total;
    its ceiling is the Spearman-Brown reliability 2r / (1 + r)."""
    y1, y2 = np.asarray(y1, float), np.asarray(y2, float)
    r = float(np.corrcoef(y1, y2)[0, 1])
    ceiling = 2 * r / (1 + r) if halves_of_target else r
    return {"n": len(y1), "r": r, "ceiling_r2": ceiling, "other_measurement_r2": r * r}


def counts_ceiling(y, exposure=None):
    y = np.asarray(y, float)
    var = y.var()
    if var == 0:
        raise SystemExit("every count is the same")
    # Poisson noise has variance equal to the expected count; its average is the mean count,
    # with or without exposure.
    noise = y.mean()
    out = {"n": len(y), "mean": float(y.mean()), "variance": float(var),
           "dispersion": float(var / y.mean()) if y.mean() > 0 else float("nan"),
           "ceiling_r2": float(1 - noise / var)}
    if exposure is not None:
        e = np.asarray(exposure, float)
        out["rate_mean"] = float(y.sum() / e.sum())
    return out


def rounding_ceiling(y, step):
    y = np.asarray(y, float)
    noise = step * step / 12.0
    return {"n": len(y), "variance": float(y.var()), "noise_variance": noise,
            "ceiling_r2": float(1 - noise / y.var())}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="kind", required=True)
    r = sub.add_parser("repeat")
    r.add_argument("table")
    r.add_argument("col1")
    r.add_argument("col2")
    r.add_argument("--halves", action="store_true",
                   help="the two columns are halves of the target, whose total is predicted")
    r.add_argument("--weight", help="a count of measurements; report the ceiling by bands of it")
    r.add_argument("--bands", type=float, nargs="+", default=[1, 10, 30, 100])
    c = sub.add_parser("counts")
    c.add_argument("table")
    c.add_argument("count")
    c.add_argument("--exposure")
    c.add_argument("--by", help="report the ceiling within each value of this column too")
    d = sub.add_parser("rounding")
    d.add_argument("table")
    d.add_argument("col")
    d.add_argument("--step", type=float, required=True)
    a = p.parse_args()

    import duckdb

    def column(*cols):
        t = duckdb.sql("select " + ", ".join(f'"{x}"' for x in cols)
                       + f" from '{a.table}'").fetchnumpy()
        for k, v in t.items():
            if np.ma.isMaskedArray(v) and v.mask.any():
                raise SystemExit(f"{k} has {int(v.mask.sum())} missing values; drop those rows first")
        return [np.asarray(t[x]) for x in cols]

    if a.kind == "repeat":
        cols = [a.col1, a.col2] + ([a.weight] if a.weight else [])
        vals = column(*cols)
        y1, y2 = vals[0].astype(float), vals[1].astype(float)
        res = repeat_ceiling(y1, y2, a.halves)
        print(f"units: {res['n']}, r {res['r']:.3f}: ceiling R2 {res['ceiling_r2']:.3f}, "
              f"R2 of the other measurement {res['other_measurement_r2']:.3f}")
        if a.weight:
            w = vals[2].astype(float)
            for lo in a.bands:
                m = w >= lo
                if m.sum() > 2:
                    rb = repeat_ceiling(y1[m], y2[m], a.halves)
                    print(f"  {a.weight} >= {lo:g}: units {rb['n']}, ceiling R2 {rb['ceiling_r2']:.3f}")
    elif a.kind == "counts":
        cols = [a.count] + ([a.exposure] if a.exposure else []) + ([a.by] if a.by else [])
        vals = column(*cols)
        y = vals[0].astype(float)
        e = vals[1].astype(float) if a.exposure else None
        res = counts_ceiling(y, e)
        print(f"units: {res['n']}, mean {res['mean']:.4g}, variance {res['variance']:.4g}, "
              f"dispersion {res['dispersion']:.3g}: ceiling R2 {res['ceiling_r2']:.3f}")
        if a.by:
            by = vals[-1]
            for g in np.unique(by):
                m = by == g
                if y[m].var() > 0:
                    rg = counts_ceiling(y[m], e[m] if e is not None else None)
                    print(f"  {a.by} {g}: units {rg['n']}, mean {rg['mean']:.3g}, "
                          f"ceiling R2 {rg['ceiling_r2']:.3f}")
    else:
        (y,) = column(a.col)
        res = rounding_ceiling(y.astype(float), a.step)
        print(f"units: {res['n']}, variance {res['variance']:.4g}, rounding noise "
              f"{res['noise_variance']:.4g}: ceiling R2 {res['ceiling_r2']:.4f}")


if __name__ == "__main__":
    main()

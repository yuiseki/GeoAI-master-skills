"""Past-only features for unit x period tables: lags, rolling means and totals before each period.

For each row (unit u, period t), every feature uses only rows of the same unit with periods
before t:
    lag{k}        the value at period t - k (NaN if that period is missing)
    mean{w}       the mean of the values at periods t - w .. t - 1 (NaN unless all w are present)
    total_before  the sum of all values at periods before t (0 for the first period)
The value at t itself never enters, so the features are safe to predict the value at t.
Periods are integers (years, or months counted from a start); a missing period is a gap, not zero.

Usage:
    uvx --with numpy --with duckdb --with pyarrow python lag_features.py TABLE UNIT TIME VALUE \
        --lags 1 2 12 --windows 3 12 [--cumulative] --out features.parquet
"""

import argparse

import numpy as np


def lag_features(unit, time, value, lags=(1,), windows=(), cumulative=False):
    unit, time, value = np.asarray(unit), np.asarray(time).astype(int), np.asarray(value, float)
    n = len(value)
    out = {f"lag{k}": np.full(n, np.nan) for k in lags}
    out.update({f"mean{w}": np.full(n, np.nan) for w in windows})
    if cumulative:
        out["total_before"] = np.zeros(n)
    for u in np.unique(unit):
        idx = np.flatnonzero(unit == u)
        at = {int(time[i]): value[i] for i in idx}
        if len(at) != len(idx):
            raise SystemExit(f"unit {u} has two rows for one period")
        for i in idx:
            t = int(time[i])
            for k in lags:
                if t - k in at:
                    out[f"lag{k}"][i] = at[t - k]
            for w in windows:
                past = [at.get(t - j) for j in range(1, w + 1)]
                if all(v is not None for v in past):
                    out[f"mean{w}"][i] = float(np.mean(past))
            if cumulative:
                out["total_before"][i] = float(sum(v for s, v in at.items() if s < t))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("unit")
    p.add_argument("time")
    p.add_argument("value")
    p.add_argument("--lags", type=int, nargs="*", default=[1])
    p.add_argument("--windows", type=int, nargs="*", default=[])
    p.add_argument("--cumulative", action="store_true")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    import duckdb
    import pyarrow as pa

    t = duckdb.sql(f'select "{a.unit}", "{a.time}", "{a.value}" from \'{a.table}\'').fetchnumpy()
    u, tm, v = (np.asarray(t[c]) for c in (a.unit, a.time, a.value))
    f = lag_features(u, tm, v, a.lags, a.windows, a.cumulative)
    cols = {a.unit: u.astype(str), a.time: tm, a.value: v.astype(float), **f}
    out = pa.table(cols)
    duckdb.sql(f"copy (select * from out order by 1, 2) to '{a.out}' (format parquet)")
    print(f"rows {len(v)}, units {len(np.unique(u))}; " + ", ".join(
        f"{k}: {int(np.isnan(x).sum())} NaN" for k, x in f.items()))


if __name__ == "__main__":
    main()

"""Find level jumps in many series before forecasting them.

For each series, the log change from one period to the next is compared with that series' own
usual change (its median, and a robust spread from the median absolute deviation). A change
that is far outside both the spread and a minimum size is a break: a data revision, a
definition change, a shock, or a series that changed what it counts.

The total over all series is checked too, like for like (only the series present in both
periods), next to the raw total. A raw total that jumps while the like-for-like total does not
means series entered or left; a smooth total can hide breaks in single series.

Usage:
    uvx --with numpy --with duckdb python series_breaks.py TABLE SERIES TIME VALUE [--top 15] \
        [--min-jump 0.15] [--mad 5] [--min-level 0]
"""

import argparse

import numpy as np

SIGMA = 1.4826  # MAD to standard deviation for a normal distribution


def _log_changes(values):
    v = np.where(values > 0, values, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.diff(np.log(v), axis=-1)


def _far(g, min_jump, mad_k):
    """True where a change is far from the series' own median change."""
    ok = ~np.isnan(g)
    if ok.sum() < 3:
        return np.zeros(g.shape, bool)
    med = np.median(g[ok])
    spread = SIGMA * np.median(np.abs(g[ok] - med))
    out = np.zeros(g.shape, bool)
    out[ok] = np.abs(g[ok] - med) > max(min_jump, mad_k * spread)
    return out


def find_breaks(keys, times, values, min_jump=0.15, mad_k=5.0, min_level=0.0):
    """List of (key, time, log change), the largest departures first. values: series x time.

    Changes between values that are both below `min_level` are ignored: a count that goes from 3 to
    300 is noise from small numbers, not a break.
    """
    values = np.asarray(values, float)
    g = _log_changes(values)
    if min_level > 0:
        big = np.fmax(values[:, 1:], values[:, :-1]) >= min_level
        g = np.where(big, g, np.nan)
    found = []
    for i, key in enumerate(keys):
        flagged = _far(g[i], min_jump, mad_k)
        med = np.nanmedian(g[i]) if (~np.isnan(g[i])).any() else 0.0
        for j in np.flatnonzero(flagged):
            found.append((abs(g[i, j] - med), key, times[j + 1], float(g[i, j])))
    found.sort(key=lambda x: -x[0])
    return [(k, t, g_) for _, k, t, g_ in found]


def aggregate_breaks(values, times, min_jump=0.15, mad_k=5.0):
    """The total over series, period by period: raw change, like-for-like change, entries, exits."""
    values = np.asarray(values, float)
    present = ~np.isnan(values) & (values >= 0)
    clean = np.where(present, values, 0.0)
    rows = []
    for j in range(1, values.shape[1]):
        both = present[:, j] & present[:, j - 1]
        s_prev, s_now = clean[:, j - 1].sum(), clean[:, j].sum()
        l_prev, l_now = clean[both, j - 1].sum(), clean[both, j].sum()
        rows.append({
            "time": times[j],
            "raw_change": float(np.log(s_now / s_prev)) if s_prev > 0 and s_now > 0 else float("nan"),
            "like_for_like_change": float(np.log(l_now / l_prev)) if l_prev > 0 and l_now > 0 else float("nan"),
            "entering": int((present[:, j] & ~present[:, j - 1]).sum()),
            "leaving": int((present[:, j - 1] & ~present[:, j]).sum()),
        })
    lfl = np.array([r["like_for_like_change"] for r in rows])
    raw = np.array([r["raw_change"] for r in rows])
    for r, f, rf in zip(rows, _far(lfl, min_jump, mad_k), _far(raw, min_jump, mad_k)):
        r["flag"], r["raw_flag"] = bool(f), bool(rf)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("series")
    p.add_argument("time")
    p.add_argument("value")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--min-jump", type=float, default=0.15)
    p.add_argument("--mad", type=float, default=5.0)
    p.add_argument("--min-level", type=float, default=0.0,
                   help="ignore changes between values that are both below this (counts that start from tiny numbers)")
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.series}", "{a.time}", "{a.value}" from \'{a.table}\'').fetchall()
    keys = sorted({str(r[0]) for r in rows})
    times = sorted({r[1] for r in rows})
    ki, ti = {k: i for i, k in enumerate(keys)}, {t: i for i, t in enumerate(times)}
    values = np.full((len(keys), len(times)), np.nan)
    for k, t, v in rows:
        if v is not None:
            values[ki[str(k)], ti[t]] = float(v)
    if isinstance(times[0], int) and len(times) != times[-1] - times[0] + 1:
        print("note: the time axis has gaps; a gap is read as a missing value, not as the next period")
    print(f"series {len(keys)}, periods {len(times)} ({times[0]} to {times[-1]})")

    print("\ntotal over series, the 5 largest like-for-like changes (like for like = only series present in both periods)")
    print("time        raw change  like-for-like  entering  leaving")
    rows_total = aggregate_breaks(values, times, a.min_jump, a.mad)
    biggest = sorted((r for r in rows_total if not np.isnan(r["like_for_like_change"])),
                     key=lambda r: -abs(r["like_for_like_change"]))[:5]
    for r in sorted(biggest, key=lambda r: r["time"]):
        mark = "  <- jump" if r["flag"] else ("  <- raw total jumps, series entered or left" if r["raw_flag"] else "")
        print(f"{r['time']!s:<10}  {r['raw_change']:+.3f}      {r['like_for_like_change']:+.3f}"
              f"          {r['entering']:>4}      {r['leaving']:>4}{mark}")
    found = find_breaks(keys, times, values, a.min_jump, a.mad, a.min_level)
    print(f"\nbreaks in single series: {len(found)} (log change; +0.693 is a doubling), largest first")
    for k, t, g in found[:a.top]:
        print(f"  {k}  {t}  {g:+.3f}  ({np.exp(g) - 1:+.1%})")


if __name__ == "__main__":
    main()

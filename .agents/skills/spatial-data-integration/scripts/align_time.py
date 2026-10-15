"""Join values to rows by time, and move values from old area codes to current ones.

    asof_join     for each row, the value of the same key with the latest time at or before the row's time
                  (backward only: never a later value). Choose which time: the reference time (when the
                  value describes) or the publication time (when it could be known). gap_days says how old
                  the value is; tolerance_days leaves values older than that unmatched (None, not a number).
    nearest_join  the value nearest in time, either side, with future=True where it is later than the row.
                  For describing a period when values change slowly, never for a forecast or a model that
                  must only use the past.
    harmonize     values by old code -> values by new code through a crosswalk (old, new, weight). A merge
                  is weight 1 from each old unit; a split shares an old unit by stated weights (area,
                  population), which is an assumption to write down. Each old unit's weights must add up
                  to 1; codes missing from the crosswalk are listed (unmapped), not dropped silently, and
                  new units that some of their old units did not reach are listed (incomplete), since
                  their sums are partial.
Two values for the same key and time stop the joins rather than one being picked silently.

Usage (as a module):
    asof_join(rows, "date", census, "published", key="key")
"""

import bisect
from collections import defaultdict


def _index(values, time, key):
    by = defaultdict(list)
    for v in values:
        by[v[key]].append(v)
    for k in by:
        by[k].sort(key=lambda v: v[time])
        times = [v[time] for v in by[k]]
        if len(set(times)) != len(times):
            raise ValueError(f"key {k!r} has two values for the same time; pick one (a later version?) first")
    return by


def asof_join(rows, row_time, values, value_time, key="key", tolerance_days=None):
    by = _index(values, value_time, key)
    out = []
    for r in rows:
        cand = by.get(r[key], [])
        i = bisect.bisect_right([v[value_time] for v in cand], r[row_time]) - 1
        hit = cand[i] if i >= 0 else None
        gap = (r[row_time] - hit[value_time]).days if hit else None
        if hit and tolerance_days is not None and gap > tolerance_days:
            hit, gap = None, None
        out.append({**r, "value": hit["value"] if hit else None,
                    "value_time": hit[value_time] if hit else None, "gap_days": gap})
    return out


def nearest_join(rows, row_time, values, value_time, key="key"):
    by = _index(values, value_time, key)
    out = []
    for r in rows:
        cand = by.get(r[key], [])
        if not cand:
            out.append({**r, "value": None, "value_time": None, "gap_days": None, "future": None})
            continue
        best = min(cand, key=lambda v: abs((v[value_time] - r[row_time]).days))
        gap = (r[row_time] - best[value_time]).days
        out.append({**r, "value": best["value"], "value_time": best[value_time], "gap_days": gap,
                    "future": gap < 0})
    return out


def harmonize(values, crosswalk):
    weights = defaultdict(float)
    for old, _, w in crosswalk:
        weights[old] += w
    bad = sorted(k for k, w in weights.items() if abs(w - 1) > 1e-9)
    if bad:
        raise ValueError(f"weights of these old units do not add up to 1: {bad}")
    out = defaultdict(float)
    for old, new, w in crosswalk:
        if old in values:
            out[new] += values[old] * w
    missing = defaultdict(list)
    for old, new, _ in crosswalk:
        if old not in values:
            missing[new].append(old)
    return {"values": dict(out), "unmapped": sorted(k for k in values if k not in weights),
            "incomplete": {k: sorted(v) for k, v in missing.items() if k in out}}

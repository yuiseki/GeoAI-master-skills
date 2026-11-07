"""Pieces for predicting where a moving object ends up from the start of its track (a prefix), tested in
test_trajectory.py. Tracks are stored flat: lat, lon (one array each, all tracks one after another) and off (track i is
lat[off[i]:off[i+1]]), with one point every `step` seconds.

  haversine, equirectangular   distance in km on a 6371 km sphere. Score with haversine; equirectangular is the cheaper
                               training loss (within 0.1% of haversine at city scale)
  parse_polyline               '[[lon, lat], ...]' -> array (n, 2), lon first
  snapshot_cut                 the tracks running at given times, cut at the first such time: a test built like a
                               snapshot of the fleet. Long tracks are caught more often, as in real use
  uniform_cuts                 n times drawn uniformly in [begin, end) with a fixed seed
  first_last_k                 the first k and last k points of one prefix, repeating the end points when short
  batch_first_last             the same for many prefixes at once, (batch, 2k, 2) of (lat, lon)
  last_point                   the last known point of each prefix: the baseline every model must beat
  sample_prefixes              training prefixes drawn uniformly from all prefixes of all tracks (the same distribution
                               as snapshot_cut gives)
  time_features                quarter hour, weekday, week of the year in the local time zone
  boot_by_group                95% interval of a mean, resampling whole groups (the cut times)
  paired_difference            mean of a - b on the same prefixes, with the interval resampling groups for both at once

Example (the destination of each test prefix, scored against the last point):

    trip, n, at = snapshot_cut(starts, lens, uniform_cuts(t0, t1, 500, seed=42), return_cut=True)
    y = np.stack([lat[off[trip + 1] - 1], lon[off[trip + 1] - 1]], 1)
    p = last_point(lat, lon, off, trip, n)
    err = haversine(p[:, 0], p[:, 1], y[:, 0], y[:, 1])
    print(err.mean(), boot_by_group(err, at))
"""

import json

import numpy as np

R = 6371.0


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def equirectangular(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    x = np.radians(np.asarray(lon2) - np.asarray(lon1)) * np.cos((p1 + p2) / 2)
    return R * np.sqrt(x * x + (p2 - p1) ** 2)


def parse_polyline(s):
    return np.asarray(json.loads(s), dtype="float64").reshape(-1, 2)


def snapshot_cut(starts, lens, cuts, step=15, return_cut=False):
    """starts: start times (s); lens: number of points. A track runs from its start to start + step (len - 1).
    Returns (track indices, number of known points[, the cut time]) for the tracks running at some cut."""
    starts, lens = np.asarray(starts), np.asarray(lens)
    ends = starts + step * (lens - 1)
    taken = np.zeros(len(starts), dtype=bool)
    trip, n, at = [], [], []
    for c in sorted(cuts):
        hit = np.flatnonzero((starts <= c) & (ends >= c) & (lens > 0) & ~taken)
        taken[hit] = True
        trip.append(hit)
        n.append((c - starts[hit]) // step + 1)
        at.append(np.full(len(hit), c))
    out = np.concatenate(trip).astype(np.int64), np.concatenate(n).astype(np.int64)
    return out + (np.concatenate(at).astype(np.int64),) if return_cut else out


def uniform_cuts(begin, end, n, seed):
    return np.random.default_rng(seed).integers(begin, end, n)


def first_last_k(points, k):
    m = len(points)
    return np.concatenate([points[np.minimum(np.arange(k), m - 1)], points[np.maximum(np.arange(m - k, m), 0)]])


def batch_first_last(lat, lon, off, trip, n, k):
    s = off[trip][:, None]
    i_first = np.minimum(np.arange(k)[None, :], n[:, None] - 1)
    i_last = np.maximum(n[:, None] - k + np.arange(k)[None, :], 0)
    idx = s + np.concatenate([i_first, i_last], 1)
    return np.stack([lat[idx], lon[idx]], -1)


def last_point(lat, lon, off, trip, n):
    i = off[trip] + n - 1
    return np.stack([lat[i], lon[i]], 1).astype("float64")


def sample_prefixes(lens, size, rng, cum=None):
    """Pass cum = np.cumsum(lens) when drawing many batches: it is the slow part."""
    lens = np.asarray(lens)
    cum = np.cumsum(lens) if cum is None else cum
    flat = rng.integers(0, cum[-1], size)
    trip = np.searchsorted(cum, flat, side="right")
    return trip, flat - (cum[trip] - lens[trip]) + 1


def time_features(ts, tz):
    """Unix seconds -> (quarter hour 0..95, weekday 0=Mon..6, week of the year 0..51) in the time zone tz."""
    import pandas as pd
    t = pd.to_datetime(np.asarray(ts), unit="s", utc=True).tz_convert(tz)
    return ((t.hour * 4 + t.minute // 15).to_numpy(), t.day_of_week.to_numpy(),
            np.minimum((t.day_of_year.to_numpy() - 1) // 7, 51))


def boot_by_group(x, group, reps=2000, seed=0):
    rng = np.random.default_rng(seed)
    g = np.unique(group, return_inverse=True)[1]
    sums, cnt = np.bincount(g, x), np.bincount(g)
    idx = rng.integers(0, len(sums), (reps, len(sums)))
    return tuple(np.percentile(sums[idx].sum(1) / cnt[idx].sum(1), [2.5, 97.5]))


def paired_difference(a, b, group, reps=2000, seed=0):
    d = np.asarray(a) - np.asarray(b)
    lo, hi = boot_by_group(d, group, reps, seed)
    return float(d.mean()), float(lo), float(hi)

"""Pieces of EXPERIMENT_PLAN.md, tested in test_porto.py.

  haversine, equirectangular   distance in km on a 6371 km sphere (the competition metric is haversine)
  parse_polyline               the POLYLINE column: [[lon, lat], ...] -> array (n, 2), one point every 15 s
  snapshot_cut                 trips running at given times, cut at the first such time (the competition's test design)
  uniform_cuts                 n times drawn uniformly in [begin, end) with a fixed seed
  first_last_k                 the first k and last k points of a prefix, padding by repeating the end points
  sample_prefixes              prefixes drawn uniformly from all prefixes of all trips (trip with probability
                               proportional to its length, then a uniform cut)
"""

import json

import numpy as np

R = 6371.0
STEP = 15


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


def snapshot_cut(starts, lens, cuts, return_cut=False):
    """starts: trip start times (s); lens: number of points. A trip runs from its start to start + 15 (len - 1).
    Returns (trip indices, number of known points) for the trips running at some cut, cut at the first such cut."""
    starts, lens = np.asarray(starts), np.asarray(lens)
    ends = starts + STEP * (lens - 1)
    taken = np.zeros(len(starts), dtype=bool)
    trip, n, at = [], [], []
    for c in sorted(cuts):
        hit = np.flatnonzero((starts <= c) & (ends >= c) & (lens > 0) & ~taken)
        taken[hit] = True
        trip.append(hit)
        n.append((c - starts[hit]) // STEP + 1)
        at.append(np.full(len(hit), c))
    out = np.concatenate(trip).astype(np.int64), np.concatenate(n).astype(np.int64)
    return out + (np.concatenate(at).astype(np.int64),) if return_cut else out


def uniform_cuts(begin, end, n, seed):
    return np.random.default_rng(seed).integers(begin, end, n)


def first_last_k(points, k):
    m = len(points)
    first = points[np.minimum(np.arange(k), m - 1)]
    last = points[np.maximum(np.arange(m - k, m), 0)]
    return np.concatenate([first, last])


def sample_prefixes(lens, size, rng, cum=None):
    lens = np.asarray(lens)
    cum = np.cumsum(lens) if cum is None else cum
    flat = rng.integers(0, cum[-1], size)            # one of all prefixes
    trip = np.searchsorted(cum, flat, side="right")
    n = flat - (cum[trip] - lens[trip]) + 1
    return trip, n


def batch_first_last(lat, lon, off, trip, n, k):
    """For prefixes (trip, n known points): (batch, 2k, 2) of (lat, lon), as first_last_k on each prefix."""
    s = off[trip][:, None]
    i_first = np.minimum(np.arange(k)[None, :], n[:, None] - 1)
    i_last = np.maximum(n[:, None] - k + np.arange(k)[None, :], 0)
    idx = s + np.concatenate([i_first, i_last], 1)
    return np.stack([lat[idx], lon[idx]], -1)


def time_features(ts):
    """Unix seconds -> (quarter hour 0..95, weekday 0=Mon..6, week of the year 0..51) in Porto local time."""
    import pandas as pd
    t = pd.to_datetime(np.asarray(ts), unit="s", utc=True).tz_convert("Europe/Lisbon")
    q = (t.hour * 4 + t.minute // 15).to_numpy()
    dow = t.day_of_week.to_numpy()
    week = np.minimum((t.day_of_year.to_numpy() - 1) // 7, 51)
    return q, dow, week

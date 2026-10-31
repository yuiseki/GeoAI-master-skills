"""Reading the flood record's text columns, the overfloor share, resampling by disaster day, and the nearest JMA station.
Rules are fixed in EXPERIMENT_PLAN.md (measuring rules)."""
import math
import re

import numpy as np

NUM = re.compile(r"^-?[0-9]+(\.[0-9]+)?")


def rain60(v):
    """Leading number of nro_60min; a value starting with a bracket, a dash or blank is missing."""
    m = NUM.match(v.strip()) if isinstance(v, str) else None
    return float(m.group()) if m else None


def count(v):
    """Leading integer of a building count such as '12(2)'; 0 when unreadable."""
    m = re.match(r"^[0-9]+", v.strip()) if isinstance(v, str) else None
    return int(m.group()) if m else 0


def share(d):
    """Overfloor buildings over overfloor plus underfloor buildings, pooled over the rows of d."""
    den = d["utf"].sum() + d["otf"].sum()
    return d["otf"].sum() / den if den else np.nan


def boot_by_day(d, stat, reps=2000, seed=0, day="day"):
    """stat over resamples that draw whole disaster days with replacement."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in d.groupby(day)}
    keys = np.array(list(groups))
    out = []
    for _ in range(reps):
        pick = rng.choice(keys, len(keys))
        out.append(stat(_concat([groups[k] for k in pick])))
    return np.array(out, float)


def _concat(parts):
    import pandas as pd
    return pd.concat(parts, ignore_index=True)


def drop_one_day(d, stat, day="day"):
    return {k: stat(d[d[day] != k]) for k in sorted(d[day].unique())}


def km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def nearest_station(lon, lat, st):
    """(station_id, km, max1h) of the nearest station in st (columns station_id, lon, lat, max1h) with a value."""
    st = st[st["max1h"].notna()]
    dist = [km(lon, lat, a, b) for a, b in zip(st["lon"], st["lat"])]
    i = int(np.argmin(dist))
    return st["station_id"].iloc[i], dist[i], float(st["max1h"].iloc[i])

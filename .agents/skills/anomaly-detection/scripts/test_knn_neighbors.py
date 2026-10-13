"""uvx --with numpy --with scikit-learn --with pytest pytest test_knn_neighbors.py"""

import numpy as np

from knn_neighbors import knn_neighbors


def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def test_matches_brute_force_at_high_latitude_and_excludes_self():
    rng = np.random.default_rng(0)
    lon, lat = rng.uniform(-30, 30, 60), rng.uniform(60, 75, 60)
    got = knn_neighbors(lon, lat, 4)
    for i in range(60):
        d = haversine(lon[i], lat[i], lon, lat)
        d[i] = np.inf
        assert sorted(got[i].tolist()) == sorted(np.argsort(d)[:4].tolist())
        assert i not in got[i]

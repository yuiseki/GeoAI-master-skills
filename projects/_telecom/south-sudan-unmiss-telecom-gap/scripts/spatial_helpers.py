"""Small, deterministic spatial helpers for this project."""

import numpy as np
from pyproj import Geod

_WGS84 = Geod(ellps="WGS84")


def geodesic_distance_km(lon1, lat1, lon2, lat2):
    """Return the WGS84 ellipsoidal distance in kilometres."""
    _, _, distance_m = _WGS84.inv(lon1, lat1, lon2, lat2)
    return np.asarray(distance_m, dtype=float) / 1000.0


def within_distance(distance_km, threshold_km):
    """Classify geometric proximity only; this is not a coverage test."""
    return bool(distance_km <= threshold_km)

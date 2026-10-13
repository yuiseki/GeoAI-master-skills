"""k nearest neighbours of points on the sphere (great-circle distance)."""

import numpy as np
from sklearn.neighbors import BallTree


def knn_neighbors(lon, lat, k):
    """For each unit, the indices of its k nearest other units."""
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    # BallTree's haversine takes (latitude, longitude) in radians.
    tree = BallTree(np.radians(np.c_[lat, lon]), metric="haversine")
    _, idx = tree.query(np.radians(np.c_[lat, lon]), k=k + 1)
    out = []
    for i, row in enumerate(idx):
        row = [j for j in row if j != i][:k]
        out.append(np.array(row, int))
    return out

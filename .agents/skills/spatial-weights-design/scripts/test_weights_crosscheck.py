"""uvx --with numpy --with scipy --with duckdb --with pyarrow --with libpysal --with esda --with pytest pytest test_weights_crosscheck.py

weights against libpysal 4.15 (KNN, DistanceBand) and esda 2.10 (Moran with binary and row-standardised
weights), on points in a plane.
"""

import numpy as np
import pytest
from esda import Moran
from libpysal.weights import KNN, DistanceBand, W

from weights import band, distances, knn, moran_i, standardise


def _points(seed, n=150):
    rng = np.random.default_rng(seed)
    xy = np.r_[rng.normal(0, 1, (n // 2, 2)), rng.uniform(-8, 8, (n - n // 2, 2))]
    return xy, xy[:, 0] + rng.normal(size=n)


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("k", [3, 8])
def test_knn_sets_match_libpysal(seed, k):
    xy, _ = _points(seed)
    nb, _ = knn(distances(xy[:, 0], xy[:, 1]), k)
    ref = KNN.from_array(xy, k=k)
    assert all(set(nb[i].tolist()) == set(ref.neighbors[i]) for i in range(len(xy)))


@pytest.mark.parametrize("seed", range(3))
def test_distance_band_sets_match_libpysal(seed):
    xy, _ = _points(seed)
    nb, _ = band(distances(xy[:, 0], xy[:, 1]), 1.0)
    ref = DistanceBand.from_array(xy, threshold=1.0, binary=True, silence_warnings=True)
    assert all(set(nb[i].tolist()) == set(ref.neighbors[i]) for i in range(len(xy)))


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("kind,transform", [("binary", "B"), ("row", "R")])
def test_moran_matches_esda(seed, kind, transform):
    xy, v = _points(seed)
    nb, _ = knn(distances(xy[:, 0], xy[:, 1]), 5)
    w = W({i: list(map(int, n)) for i, n in enumerate(nb)}, silence_warnings=True)
    w.transform = transform
    ours = moran_i(v, standardise(nb, [np.ones(len(n)) for n in nb], kind))
    assert ours == pytest.approx(Moran(v, w, permutations=0).I, rel=1e-12)

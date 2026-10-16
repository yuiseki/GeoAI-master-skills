"""uvx --with numpy --with scipy --with shapely --with duckdb --with pyarrow --with pytest pytest test_weights.py"""

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from weights import band, describe, distances, jaccard, knn, moran_i, standardise


def _line(xs):
    xs = np.asarray(xs, float)
    return distances(xs, np.zeros_like(xs))


def test_knn_on_a_line_and_its_asymmetry():
    # Points at 0, 1, 3, 10: the nearest of 10 is 3, but the nearest of 3 is 1.
    nb, d = knn(_line([0, 1, 3, 10]), 1)
    assert [list(n) for n in nb] == [[1], [0], [1], [2]]
    s = describe(nb, d)
    assert s["asymmetric_share"] == pytest.approx(2 / 4)  # 2 -> 1 and 3 -> 2 are not returned
    assert s["distance_max"] == pytest.approx(7)


def test_distance_band_leaves_islands_where_points_are_sparse():
    nb, _ = band(_line([0, 1, 2, 10, 11, 30]), 1.5)
    s = describe(nb)
    assert s["islands"] == 1 and s["components"] == 3
    assert s["degree_min"] == 0 and s["degree_max"] == 2
    assert s["band_without_islands"] == pytest.approx(19)  # the largest nearest-neighbour distance


def test_great_circle_distances_at_high_latitude():
    D = distances(np.array([0.0, 1.0]), np.array([60.0, 60.0]), lonlat=True)
    assert D[0, 1] == pytest.approx(55.6, rel=0.01)  # km: one degree of longitude at 60 N


def test_decay_weights_inside_the_band():
    nb, w = band(_line([0, 1, 2, 4]), 2.5, decay="power", alpha=1.0)
    assert dict(zip(nb[0].tolist(), w[0].tolist())) == {1: pytest.approx(1.0), 2: pytest.approx(0.5)}
    nb, w = band(_line([0, 1, 2, 4]), 2.5, decay="exponential", scale=1.0)
    assert dict(zip(nb[0].tolist(), w[0].tolist()))[2] == pytest.approx(math.exp(-2))


def test_standardisations():
    nb = [np.array([1, 2]), np.array([0]), np.array([0]), np.array([], int)]
    w = [np.ones(2), np.ones(1), np.ones(1), np.ones(0)]
    W = standardise(nb, w, "row").toarray()
    assert W.sum(1).tolist() == pytest.approx([1, 1, 1, 0])  # an island keeps a zero row
    B = standardise(nb, w, "binary").toarray()
    assert B.sum() == 4
    S = standardise(nb, w, "symmetric").toarray()
    assert np.allclose(S, S.T)


def test_row_standardisation_changes_moran_when_degrees_differ():
    # A star: a hub with 6 spokes, values opposite to the hub's. In binary weights the hub's six pairs
    # all count; row-standardised, each spoke's single neighbour (the hub) weighs as much as the hub's six.
    nb = [np.arange(1, 7)] + [np.array([0])] * 6 + [np.array([8]), np.array([7])]
    w = [np.ones(len(n)) for n in nb]
    x = np.array([10.0, 0, 0, 0, 0, 0, 0, 5, 5.5])
    ib = moran_i(x, standardise(nb, w, "binary"))
    ir = moran_i(x, standardise(nb, w, "row"))
    assert ib < 0 and ir < 0
    assert abs(ib - ir) > 0.1


def test_jaccard_of_two_neighbour_sets():
    a = [np.array([1, 2]), np.array([0])]
    b = [np.array([1]), np.array([0])]
    assert jaccard(a, b) == pytest.approx((0.5 + 1) / 2)


def test_knn_refuses_k_not_below_the_number_of_points():
    with pytest.raises(SystemExit):
        knn(_line([0, 1, 2]), 3)


def test_cli_describes_each_candidate_and_compares_them(tmp_path):
    rng = np.random.default_rng(0)
    xy = np.r_[rng.normal(0, 1, (80, 2)), rng.uniform(-30, 30, (20, 2))]  # a dense core and a sparse ring
    v = xy[:, 0] + rng.normal(size=100)
    (tmp_path / "p.csv").write_text("id,x,y,v\n" + "\n".join(f"{i},{a},{b},{c}" for i, ((a, b), c) in
                                                            enumerate(zip(xy, v))) + "\n")
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("weights.py")), str(tmp_path / "p.csv"), "id",
                          "--x", "x", "--y", "y", "--crs-units", "m", "--knn", "4", "8", "--band", "2",
                          "--value", "v", "--out", str(tmp_path / "w.parquet")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    for label in ("knn 4", "knn 8", "band 2"):
        assert label in out.stdout
    assert "islands" in out.stdout and "Jaccard" in out.stdout and "Moran" in out.stdout
    assert (tmp_path / "w.parquet").exists()

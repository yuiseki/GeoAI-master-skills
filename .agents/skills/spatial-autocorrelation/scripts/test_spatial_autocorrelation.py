"""uvx --with duckdb --with scikit-learn --with esda --with libpysal --with pytest pytest test_spatial_autocorrelation.py

esda and libpysal are used only here, as an independent reference for the statistics.
"""

import math

import numpy as np
import pytest

from spatial_autocorrelation import band_neighbors, knn_neighbors, local_moran, moran

esda = pytest.importorskip("esda")
libpysal = pytest.importorskip("libpysal")


def to_w(neighbors):
    w = libpysal.weights.W({i: list(n) for i, n in enumerate(neighbors)}, silence_warnings=True)
    w.transform = "r"
    return w


def haversine_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


@pytest.fixture
def field():
    rng = np.random.default_rng(0)
    n = 200
    lon = rng.uniform(-10, 10, n)
    lat = rng.uniform(40, 60, n)
    x = lat + rng.normal(scale=2, size=n)  # a north-south gradient: positive autocorrelation
    return lon, lat, x


def test_knn_takes_the_nearest_by_great_circle_distance():
    # At 60N, 1 degree of longitude (~56 km) is nearer than 1 degree of latitude (~111 km).
    lon = np.array([0.0, 1.0, 0.0])
    lat = np.array([60.0, 60.0, 61.0])
    assert knn_neighbors(lon, lat, 1)[0].tolist() == [1]
    # Across the antimeridian.
    lon = np.array([179.9, -179.9, 170.0])
    lat = np.zeros(3)
    assert knn_neighbors(lon, lat, 1)[0].tolist() == [1]


def test_band_neighbors_match_brute_force(field):
    lon, lat, _ = field
    got = band_neighbors(lon, lat, 100, 300)
    for i in range(len(lon)):
        want = {j for j in range(len(lon)) if j != i
                and 100 < haversine_km(lon[i], lat[i], lon[j], lat[j]) <= 300}
        assert set(got[i].tolist()) == want


def test_global_moran_matches_esda(field):
    lon, lat, x = field
    nb = knn_neighbors(lon, lat, 6)
    ours = moran(x, nb, permutations=999, seed=0)
    ref = esda.Moran(x, to_w(nb), permutations=999)
    assert ours["I"] == pytest.approx(ref.I, rel=1e-9)
    assert ours["EI"] == pytest.approx(ref.EI, rel=1e-9)
    assert ours["p_sim"] <= 0.002 and ref.p_sim <= 0.002


def test_global_moran_with_islands_matches_esda(field):
    lon, lat, x = field
    nb = band_neighbors(lon, lat, 0, 60)  # some points have no neighbour this close
    assert any(len(n) == 0 for n in nb)
    ours = moran(x, nb, permutations=99, seed=0)
    ref = esda.Moran(x, to_w(nb), permutations=99)
    assert ours["I"] == pytest.approx(ref.I, rel=1e-9)


def test_random_values_show_no_autocorrelation(field):
    lon, lat, _ = field
    x = np.random.default_rng(1).normal(size=len(lon))
    r = moran(x, knn_neighbors(lon, lat, 6), permutations=999, seed=0)
    assert abs(r["I"]) < 0.1
    assert r["p_sim"] > 0.05


def test_local_moran_matches_esda(field):
    lon, lat, x = field
    nb = knn_neighbors(lon, lat, 6)
    ours = local_moran(x, nb, permutations=999, seed=0)
    ref = esda.Moran_Local(x, to_w(nb), permutations=999, seed=0, alternative="directed")
    assert ours["Is"] == pytest.approx(ref.Is, rel=1e-9)
    assert ours["q"].tolist() == ref.q.tolist()
    # Pseudo p-values are random; they should agree on which units are clearly significant.
    assert np.corrcoef(ours["p_sim"], ref.p_sim)[0, 1] > 0.9


def test_getis_ord_gi_star_matches_esda(field):
    from spatial_autocorrelation import getis_ord

    lon, lat, x = field
    nb = knn_neighbors(lon, lat, 6)
    ours = getis_ord(x, nb)
    w = libpysal.weights.W({i: list(n) for i, n in enumerate(nb)}, silence_warnings=True)
    ref = esda.G_Local(x, w, transform="B", star=True, permutations=0)
    assert ours == pytest.approx(ref.Zs, rel=1e-6)


def test_getis_ord_finds_a_planted_hotspot():
    from spatial_autocorrelation import getis_ord

    rng = np.random.default_rng(5)
    lon = rng.uniform(0, 10, 400)
    lat = rng.uniform(40, 50, 400)
    x = rng.normal(size=400)
    hot = (lon < 2) & (lat < 42)
    x[hot] += 4
    z = getis_ord(x, knn_neighbors(lon, lat, 8))
    assert z[hot].mean() > 3
    assert abs(z[~hot & (lon > 5)].mean()) < 1


def test_benjamini_hochberg_and_bonferroni_by_hand():
    from spatial_autocorrelation import adjust_p
    p = np.array([0.04, 0.01, 0.2, 0.03, 0.02])          # unsorted on purpose
    # BH: sorted 0.01 0.02 0.03 0.04 0.2 -> p * 5 / rank = 0.05 0.05 0.05 0.05 0.2, then running minimum from the top
    assert adjust_p(p, "fdr").tolist() == pytest.approx([0.05, 0.05, 0.2, 0.05, 0.05])
    assert adjust_p(p, "bonferroni").tolist() == pytest.approx([0.2, 0.05, 1.0, 0.15, 0.1])
    # 0.01 0.04 0.045: p * 3 / rank = 0.03 0.06 0.045; the 0.06 takes the smaller value above it, 0.045
    assert adjust_p(np.array([0.01, 0.04, 0.045]), "fdr").tolist() == pytest.approx([0.03, 0.045, 0.045])


def test_gi_star_p_values_are_two_sided_normal():
    from spatial_autocorrelation import gi_p_values
    assert gi_p_values(np.array([1.959964, -1.959964, 0.0])).tolist() == pytest.approx([0.05, 0.05, 1.0], abs=1e-5)


def test_correction_drops_chance_hits_and_keeps_a_planted_hotspot():
    from spatial_autocorrelation import adjust_p, getis_ord, gi_p_values
    rng = np.random.default_rng(5)
    lon, lat = rng.uniform(0, 10, 400), rng.uniform(40, 50, 400)
    noise = rng.normal(size=400)
    nb = knn_neighbors(lon, lat, 8)
    p_noise = gi_p_values(getis_ord(noise, nb))
    assert (p_noise <= 0.05).sum() > 5                         # chance alone makes "hot spots" among 400 tests
    assert (adjust_p(p_noise, "fdr") <= 0.05).sum() < (p_noise <= 0.05).sum()
    x = noise.copy()
    hot = (lon < 2) & (lat < 42)
    x[hot] += 4
    p_hot = adjust_p(gi_p_values(getis_ord(x, nb)), "fdr")
    assert (p_hot[hot] <= 0.05).mean() > 0.8

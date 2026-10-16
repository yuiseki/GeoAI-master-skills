"""uvx --with duckdb --with scikit-learn --with esda --with libpysal --with pytest pytest test_spatial_autocorrelation.py

esda and libpysal are used only here, as an independent reference for the statistics.
"""

import math

import numpy as np
import pytest

from spatial_autocorrelation import band_neighbors, bivariate_moran, general_g, knn_neighbors, local_moran, moran

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


# Getis-Ord General G


def test_general_g_matches_esda(field):
    lon, lat, x = field
    x = x - x.min() + 1  # non-negative
    nb = knn_neighbors(lon, lat, 6)
    w = libpysal.weights.W({i: list(n) for i, n in enumerate(nb)}, silence_warnings=True)
    ref = esda.G(x, w, permutations=0)
    ours = general_g(x, nb, permutations=99)
    assert ours["G"] == pytest.approx(ref.G, rel=1e-12)
    assert ours["EG"] == pytest.approx(ref.EG, rel=1e-12)


def _grid(n=20):
    r, c = np.divmod(np.arange(n * n), n)
    lon, lat = c * 0.1, 40 + r * 0.1
    return lon, lat, r, c


def test_general_g_rises_for_a_high_block_but_does_not_fall_for_a_low_block():
    # Moran's I is strongly positive for both. G is far above its expectation for a block of high values;
    # for a block of low values in a uniform high background it is still above (the highs elsewhere now
    # sit together), so G below E[G] does not mean "low values cluster".
    lon, lat, r, c = _grid()
    rng = np.random.default_rng(1)
    corner = (r < 6) & (c < 6)
    high = np.where(corner, 20 + rng.uniform(0, 1, len(r)), rng.uniform(1, 2, len(r)))
    low = np.where(corner, 0.01, 20 + rng.uniform(0, 1, len(r)))
    nb = knn_neighbors(lon, lat, 8)
    gh, gl = general_g(high, nb, 199), general_g(low, nb, 199)
    assert moran(high, nb, 199)["I"] > 0.5 and moran(low, nb, 199)["I"] > 0.5
    assert gh["G"] > 3 * gh["EG"] and gh["p_sim"] < 0.01
    assert gl["EG"] < gl["G"] < 1.2 * gl["EG"]


def test_general_g_falls_when_high_values_sit_among_low_ones():
    lon, lat, r, c = _grid()
    x = np.where((r + c) % 2 == 0, 20.0, 1.0)  # checkerboard: every rook neighbour of a high is low
    nb = knn_neighbors(lon, lat, 4)  # on this grid the 4 nearest are the rook neighbours
    g = general_g(x, nb, 199)
    assert g["G"] < 0.5 * g["EG"] and g["p_sim"] < 0.01
    assert moran(x, nb, 199)["I"] < -0.8


def test_general_g_refuses_negative_values():
    with pytest.raises(SystemExit):
        general_g(np.array([1.0, -1.0, 2.0]), [np.array([1]), np.array([0]), np.array([1])])


# bivariate Moran's I


def test_bivariate_moran_matches_esda(field):
    lon, lat, x = field
    y = np.roll(x, 3) + np.random.default_rng(5).normal(size=len(x))
    nb = knn_neighbors(lon, lat, 6)
    ref = esda.Moran_BV(x, y, to_w(nb), permutations=0)
    assert bivariate_moran(x, y, nb, permutations=9)["I_xy"] == pytest.approx(ref.I, rel=1e-12)


def test_bivariate_moran_of_a_variable_with_itself_is_its_moran(field):
    lon, lat, x = field
    nb = knn_neighbors(lon, lat, 6)
    assert bivariate_moran(x, x, nb, 9)["I_xy"] == pytest.approx(moran(x, nb, 9)["I"], rel=1e-12)


def test_bivariate_moran_rejects_too_often_when_both_variables_are_autocorrelated():
    # Two unrelated smooth fields (gradients in random directions plus noise). Shuffling y destroys its
    # autocorrelation, so the permutation test calls them related far more often than 5% of the time.
    lon, lat, _, _ = _grid(15)
    nb = knn_neighbors(lon, lat, 6)
    smooth = 0
    for seed in range(20):
        rng = np.random.default_rng(seed)
        a, b = rng.uniform(0, 2 * np.pi, 2)
        x = np.cos(a) * lon + np.sin(a) * (lat - 40) + rng.normal(scale=0.3, size=len(lon))
        y = np.cos(b) * lon + np.sin(b) * (lat - 40) + rng.normal(scale=0.3, size=len(lon))
        smooth += bivariate_moran(x, y, nb, 199, seed)["p_sim"] <= 0.05
    iid = 0
    for seed in range(40):
        rng = np.random.default_rng(100 + seed)
        iid += bivariate_moran(rng.normal(size=len(lon)), rng.normal(size=len(lon)), nb, 199, seed)["p_sim"] <= 0.05
    assert smooth >= 15  # 18 of 20 in the run that set this
    assert iid <= 6  # 2 of 40; about 5% is the nominal rate


# Nulls that keep the autocorrelation

def _grid_nb(side=15):
    nb = []
    for i in range(side * side):
        r, c = divmod(i, side)
        nb.append(np.array([j for j in (i - side, i + side, i - 1 if c else -1, i + 1 if c < side - 1 else -1)
                            if 0 <= j < side * side]))
    return nb


def _smooth(rng, side=15, scale=3.0):
    g = np.arange(side)
    X, Y = np.meshgrid(g, g)
    P = np.c_[X.ravel(), Y.ravel()]
    C = np.exp(-np.hypot(*(P[:, None] - P[None]).transpose(2, 0, 1)) / scale)
    return np.linalg.cholesky(C + 1e-9 * np.eye(len(C))) @ rng.normal(size=len(C))


def test_spectral_surrogates_keep_the_mean_variance_and_morans_i():
    from spatial_autocorrelation import msr_surrogates

    nb = _grid_nb()
    x = _smooth(np.random.default_rng(0))
    sur = msr_surrogates(x, nb, 50, seed=1)
    A = np.zeros((225, 225))
    for i, v in enumerate(nb):
        A[i, v] = 1

    def binary_i(v):
        z = v - v.mean()
        return 225 / A.sum() * z @ A @ z / (z @ z)

    np.testing.assert_allclose(sur.mean(1), x.mean(), atol=1e-10)
    np.testing.assert_allclose(sur.var(1), x.var(), rtol=1e-10)
    np.testing.assert_allclose([binary_i(s) for s in sur], binary_i(x), rtol=1e-9)
    assert np.mean([abs(np.corrcoef(s, x)[0, 1]) for s in sur]) < 0.3  # yet they are different maps


def test_spectral_randomisation_keeps_the_size_where_shuffling_does_not():
    # Two independent smooth fields: shuffling y rejects the bivariate I far too often (measured 18 of 20 in the
    # reference); surrogates that keep x's autocorrelation reject the correlation near 5%.
    from spatial_autocorrelation import bivariate_msr

    nb = _grid_nb()
    rej_msr, rej_shuffle = 0, 0
    for s in range(40):
        rng = np.random.default_rng(100 + s)
        x, y = _smooth(rng), _smooth(rng)
        r = bivariate_msr(x, y, nb, 199, seed=s)
        rej_msr += r["p_r"] <= 0.05
        rej_shuffle += bivariate_moran(x, y, nb, 199, seed=s)["p_sim"] <= 0.05
    assert rej_msr <= 6  # 40 x 0.05 = 2 expected; 6 is the 99% binomial bound
    assert rej_shuffle >= 15


def test_spectral_randomisation_still_detects_a_real_relation():
    from spatial_autocorrelation import bivariate_msr

    nb = _grid_nb()
    hits = 0
    for s in range(10):
        rng = np.random.default_rng(300 + s)
        x = _smooth(rng)
        y = x + 0.7 * _smooth(rng)
        hits += bivariate_msr(x, y, nb, 199, seed=s)["p_r"] <= 0.05
    assert hits >= 8

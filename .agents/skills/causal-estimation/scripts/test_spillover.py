"""uvx --with numpy --with pytest pytest test_spillover.py"""

import itertools

import numpy as np
import pytest

from spillover import estimate, exposure, exposure_probabilities, grid_neighbours


def test_exposure_conditions_from_own_and_neighbours_treatment():
    nb = [np.array([1]), np.array([0, 2]), np.array([1])]  # a path 0 - 1 - 2
    e = exposure(np.array([1, 0, 0]), nb)
    assert e.tolist() == ["treated, no treated neighbour", "control, treated neighbour", "control, no treated neighbour"]


def test_simulated_probabilities_match_full_enumeration():
    nb = [np.array([1]), np.array([0, 2]), np.array([1, 3]), np.array([2])]  # a path of 4
    p = 0.4
    exact = {}
    for z in itertools.product([0, 1], repeat=4):
        pr = np.prod([p if v else 1 - p for v in z])
        for i, c in enumerate(exposure(np.array(z), nb)):
            exact[(i, c)] = exact.get((i, c), 0.0) + pr
    sim = exposure_probabilities(nb, p, draws=200_000, seed=0)
    for (i, c), v in exact.items():
        assert sim["pi"][c][i] == pytest.approx(v, abs=0.005)


def _world(seed, side=20, p=0.3, direct=2.0, spill=1.0):
    nb = grid_neighbours(side)
    rng = np.random.default_rng(seed)
    base = rng.normal(size=side * side)
    z = (rng.random(side * side) < p).astype(int)
    k = np.array([z[j].sum() for j in nb])
    y = base + direct * z + spill * ((z == 0) & (k > 0))
    return y, z, nb, base


def test_naive_difference_misses_the_direct_effect_when_controls_are_contaminated():
    # Controls next to treated units gain the spillover, so the plain treated - control difference is too small.
    y, z, nb, _ = _world(0)
    naive = y[z == 1].mean() - y[z == 0].mean()
    est = estimate(y, z, nb, 0.3, draws=4000, seed=1)
    assert naive < 1.6
    assert est["direct"]["value"] == pytest.approx(2.0, abs=0.35)
    assert est["spillover"]["value"] == pytest.approx(1.0, abs=0.35)


def test_conservative_intervals_cover_over_re_randomisation():
    # Fixed potential outcomes; only the assignment is redrawn from the known design.
    side, p = 14, 0.3
    nb = grid_neighbours(side)
    rng = np.random.default_rng(5)
    base = rng.normal(size=side * side)
    probs = exposure_probabilities(nb, p, draws=4000, seed=2)
    covered_d = covered_s = 0
    for r in range(150):
        z = (np.random.default_rng(1000 + r).random(side * side) < p).astype(int)
        k = np.array([z[j].sum() for j in nb])
        y = base + 2.0 * z + 1.0 * ((z == 0) & (k > 0))
        est = estimate(y, z, nb, p, probabilities=probs)
        covered_d += abs(est["direct"]["value"] - 2) <= 1.96 * est["direct"]["se"]
        covered_s += abs(est["spillover"]["value"] - 1) <= 1.96 * est["spillover"]["se"]
    assert covered_d / 150 >= 0.93 and covered_s / 150 >= 0.93


def test_units_without_a_chance_of_a_condition_are_counted_not_dropped_silently():
    nb = [np.array([], int), np.array([2]), np.array([1])]  # unit 0 has no neighbours
    probs = exposure_probabilities(nb, 0.5, draws=2000, seed=0)
    assert probs["pi"]["control, treated neighbour"][0] == 0
    assert probs["never"]["control, treated neighbour"] == 1


def test_weights_matter_when_the_outcome_follows_the_number_of_neighbours():
    # Edge units (fewer neighbours, so less often next to a treated unit) have higher outcomes. Without the
    # exposure probabilities, the controls with no treated neighbour over-represent the edge.
    side, p = 16, 0.3
    nb = grid_neighbours(side)
    deg = np.array([len(j) for j in nb])
    vals = []
    for r in range(40):
        rng = np.random.default_rng(300 + r)
        base = 3.0 * (deg < 4) + rng.normal(size=side * side)
        z = (rng.random(side * side) < p).astype(int)
        k = np.array([z[j].sum() for j in nb])
        y = base + 2.0 * z + 1.0 * ((z == 0) & (k > 0))
        vals.append(estimate(y, z, nb, p, draws=3000, seed=r)["spillover"]["value"])
    assert np.mean(vals) == pytest.approx(1.0, abs=0.15)


def test_the_spillover_contrast_covers_only_units_that_can_have_a_treated_neighbour():
    nb = grid_neighbours(6) + [np.array([], int)] * 4  # four isolated units after a 6 x 6 grid
    rng = np.random.default_rng(9)
    z = (rng.random(40) < 0.4).astype(int)
    est = estimate(rng.normal(size=40), z, nb, 0.4, draws=2000, seed=0)
    assert est["spillover"]["units"] == 36
    assert est["direct"]["units"] == 40

"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyproj --with pyarrow --with pytest pytest test_interpolate_points.py

Expected values are worked out by hand from a few points on a line (metres, UTM 54N).
"""

import math

import duckdb
import numpy as np
import pytest

from interpolate_points import Obs, audit_duplicates, fit_variogram, kriging_variance_single, predict
from evaluate_interpolation import evaluate

X0, Y0 = 500000.0, 3950000.0


def obs(points):
    """points: list of (x, y, value) in metres from the origin."""
    return Obs(np.array([[X0 + x, Y0 + y] for x, y, _ in points], float), np.array([v for *_, v in points], float))


def q(*xs):
    return np.array([[X0 + x, Y0 + y] for x, y in xs], float)


TWO = obs([(0, 0, 10), (10, 0, 20)])


def test_nearest_takes_the_closest_observation():
    p = predict(TWO, q((3, 0), (8, 0)), "nearest")
    assert p["prediction"].tolist() == [10, 20]
    assert p["nearest_m"].tolist() == pytest.approx([3, 2])


def test_idw_weights_fall_with_distance():
    assert predict(TWO, q((2, 0)), "idw", power=1)["prediction"][0] == pytest.approx(12)        # (10/2 + 20/8) / (1/2 + 1/8)
    assert predict(TWO, q((2, 0)), "idw", power=2)["prediction"][0] == pytest.approx(10.588235, rel=1e-6)
    assert predict(TWO, q((5, 0)), "idw", power=2)["prediction"][0] == pytest.approx(15)


def test_a_query_on_an_observation_returns_its_value():
    p = predict(TWO, q((0, 0)), "idw", power=2)
    assert p["prediction"][0] == 10 and p["nearest_m"][0] == 0


def test_a_query_with_no_observation_in_reach_is_kept_and_marked():
    p = predict(TWO, q((100, 0), (1, 0)), "idw", power=2, max_dist=50)
    assert np.isnan(p["prediction"][0]) and p["status"][0] == "no_neighbors" and p["n_used"][0] == 0
    assert p["status"][1] == "ok" and len(p["prediction"]) == 2


def test_inside_hull_separates_interpolation_from_extrapolation():
    tri = obs([(0, 0, 1), (10, 0, 2), (0, 10, 3)])
    p = predict(tri, q((2, 2), (20, 20)), "nearest")
    assert p["inside_hull"].tolist() == [True, False]


def test_held_out_points_are_not_in_their_own_training_set():
    # Leave-one-out nearest on 0, 10, 30 (values 10, 20, 40): 0 -> 20, 10 -> 10, 30 -> 20. MAE = (10 + 10 + 20) / 3.
    three = obs([(0, 0, 10), (10, 0, 20), (30, 0, 40)])
    r = evaluate(three, ["nearest"], split="loo")
    assert r["nearest"]["all"]["mae"] == pytest.approx(40 / 3)


def test_every_method_is_scored_on_the_same_rows():
    three = obs([(0, 0, 10), (10, 0, 20), (30, 0, 40)])
    r = evaluate(three, ["mean", "idw"], split="loo", max_dist=15)
    # with a 15 m reach, idw cannot predict the point at 30 (the mean can); it is left out for both and counted
    assert r["mean"]["all"]["n"] == r["idw"]["all"]["n"] == 2
    assert r["unscored"] == 1


def test_distances_are_taken_in_metres_not_degrees():
    # At 60N a degree of longitude is half a degree of latitude. A is 0.015 deg east (835 m),
    # B is 0.01 deg north (1,113 m): A is nearer, though B is nearer in degrees.
    from interpolate_points import project
    ll = np.array([[1.015, 60.0], [1.0, 60.01]])
    o = Obs(project(ll, "EPSG:4326", "EPSG:32631"), np.array([1.0, 2.0]))
    p = predict(o, project(np.array([[1.0, 60.0]]), "EPSG:4326", "EPSG:32631"), "nearest")
    assert p["prediction"][0] == 1
    with pytest.raises(SystemExit):
        project(ll, "EPSG:4326", "EPSG:4326")   # a geographic CRS is refused for distances


def test_missing_values_are_dropped_and_counted_not_read_as_zero():
    from interpolate_points import clean
    o, rep = clean(np.array([[X0, Y0], [X0 + 10, Y0]]), np.array([np.nan, 20.0]))
    assert len(o.v) == 1 and rep["missing_values"] == 1
    assert predict(o, q((1, 0)), "nearest")["prediction"][0] == 20


def test_duplicate_locations_are_not_overwritten():
    xy = np.array([[X0, Y0], [X0, Y0], [X0 + 10, Y0], [X0 + 10, Y0]])
    v = np.array([10.0, 30.0, 20.0, 20.0])
    with pytest.raises(SystemExit):
        audit_duplicates(xy, v, "error")      # 10 and 30 at the same place disagree
    o, rep = audit_duplicates(xy, v, "mean")
    assert rep["same_value_duplicates"] == 1 and rep["conflicting_locations"] == 1
    assert sorted(o.v.tolist()) == [20, 20]   # (10 + 30) / 2 and 20


def test_kriging_variance_uses_nugget_sill_and_range():
    # One observation at 10 m, exponential model, nugget 1, sill 5, range 10:
    # gamma(10) = 1 + 4 (1 - e^-1) = 3.528482; the ordinary kriging variance is 2 gamma(10).
    assert kriging_variance_single(10, "exponential", 1, 5, 10) == pytest.approx(2 * (1 + 4 * (1 - math.exp(-1))), rel=1e-6)


def test_kriging_between_two_points_halfway_is_their_mean():
    p = predict(TWO, q((5, 0)), "kriging", variogram=("exponential", 0.0, 50.0, 20.0))
    assert p["prediction"][0] == pytest.approx(15)
    assert p["kriging_sd"][0] > 0


def test_variogram_of_pure_noise_is_flat():
    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 1000, (200, 2))
    v = rng.normal(0, 1, 200)                              # pure noise: flat variogram, sill near 1, nugget near sill
    model, nugget, sill, rng_ = fit_variogram(xy, v, "exponential")
    from interpolate_points import gamma
    assert sill == pytest.approx(1, abs=0.35)
    assert gamma(30.0, model, nugget, sill, rng_) >= 0.6 * sill   # no spatial structure: near pairs differ as much as far ones

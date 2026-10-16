"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pytest pytest test_st_kriging.py"""

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pytest

from st_kriging import covariance, fit, model_variogram, predict, variogram
from st_model import simulate


def _P(d):
    return np.column_stack([[d["coords"][k][0] for k in d["loc"]], [d["coords"][k][1] for k in d["loc"]], d["t"]])


def test_covariance_by_hand():
    A = np.array([[0.0, 0.0, 0.0]])
    B = np.array([[3.0, 4.0, 2.0], [0.0, 0.0, 1.0]])
    c = covariance([2.0, 5.0, 2.0], A, B)
    assert c[0, 0] == pytest.approx(2 * np.exp(-1) * np.exp(-1))
    # exponential in time at whole steps: an AR(1) with phi = exp(-1 / range_t)
    assert c[0, 1] == pytest.approx(2 * np.exp(-0.5))
    g = covariance([2.0, 5.0, 2.0], A, B, "gaussian", "gaussian")
    assert g[0, 0] == pytest.approx(2 * np.exp(-1) * np.exp(-1))


def test_without_a_nugget_kriging_returns_the_observations():
    rng = np.random.default_rng(0)
    P = np.column_stack([rng.random(20), rng.random(20), rng.integers(0, 5, 20).astype(float)])
    y = rng.normal(size=20)
    m = {"params": np.array([1.0, 0.3, 2.0, 0.0]), "space": "exponential", "time": "exponential", "mean": "constant"}
    mu, var, _ = predict(m, P, y, P[:5])
    assert mu == pytest.approx(y[:5], abs=1e-6)
    assert var == pytest.approx(np.zeros(5), abs=1e-6)


def test_far_from_every_observation_the_prediction_is_the_gls_mean_and_the_variance_grows():
    rng = np.random.default_rng(1)
    P = np.column_stack([rng.random(30), rng.random(30), np.zeros(30)])
    y = 5 + rng.normal(size=30)
    m = {"params": np.array([1.0, 1e-4, 1.0, 0.2]), "space": "exponential", "time": "exponential", "mean": "constant"}
    mu, var, var_obs = predict(m, P, y, np.array([[100.0, 100.0, 50.0]]))
    # tiny range: the covariance matrix is (sill + nugget) I, so the GLS mean is the plain mean
    assert mu[0] == pytest.approx(y.mean(), abs=1e-9)
    assert var[0] == pytest.approx(1.0 + 1.2 / 30, rel=1e-6)  # sill plus the mean's own variance
    assert var_obs[0] == pytest.approx(var[0] + 0.2)


def test_the_parameters_of_a_separable_world_are_recovered():
    # simulate("separable"): exponential in space with range 0.3, AR(1) phi 0.8 in time (range -1 / log 0.8 = 4.48),
    # sill 1, noise sd 0.5 (nugget 0.25)
    est = np.array([fit(_P(d), d["y"])["params"] for d in (simulate("separable", 30, 20, seed=s) for s in range(4))])
    sill, rs, rt, nugget = np.median(est, axis=0)
    assert sill == pytest.approx(1.0, rel=0.35)
    assert rs == pytest.approx(0.3, rel=0.4)
    assert rt == pytest.approx(-1 / np.log(0.8), rel=0.35)
    assert nugget == pytest.approx(0.25, rel=0.25)


def _world(kind, seed, n_loc=30, n_t=25):
    # Both worlds vary only along x, with the same decay in time at a fixed place (exp(-0.15 u)). In "moving" the
    # field drifts east by 0.03 a step: C = exp(-|dx - 0.03 du| / 0.2), not separable. "still" is separable:
    # exp(-|dx| / 0.2) exp(-0.15 |du|). The isotropic model is misspecified in both, by the same anisotropy.
    rng = np.random.default_rng(seed)
    xy = rng.random((n_loc, 2))
    P = np.column_stack([np.repeat(xy, n_t, 0), np.tile(np.arange(n_t, dtype=float), n_loc)])
    loc = np.repeat(np.arange(n_loc), n_t)

    def cov(A, B):
        dx, du = A[:, None, 0] - B[None, :, 0], A[:, None, 2] - B[None, :, 2]
        if kind == "moving":
            return np.exp(-np.abs(dx - 0.03 * du) / 0.2)
        return np.exp(-np.abs(dx) / 0.2) * np.exp(-0.15 * np.abs(du))

    C = cov(P, P)
    y = np.linalg.cholesky(C + 1e-8 * np.eye(len(C))) @ rng.normal(size=len(C)) + rng.normal(0, 0.5, len(C))
    return P, loc, y, cov


def test_a_moving_field_costs_the_separable_model_against_the_true_covariance():
    # Forecasting the last 5 times at known places: against kriging with the true covariance, the separable model
    # loses little when the field stands still (only the anisotropy) and much more when it moves. Its intervals
    # stay honest (they widen): the loss shows as width, not as missed coverage.
    ratio, cover = {}, {}
    for kind in ("still", "moving"):
        for s in range(3):
            P, loc, y, cov = _world(kind, s)
            te = P[:, 2] >= 20
            m = fit(P[~te], y[~te])
            mu, _, var_obs = predict(m, P[~te], y[~te], P[te])
            oracle = cov(P[te], P[~te]) @ np.linalg.solve(cov(P[~te], P[~te]) + 0.25 * np.eye((~te).sum()), y[~te])
            ratio.setdefault(kind, []).append(np.sqrt(np.mean((y[te] - mu) ** 2) / np.mean((y[te] - oracle) ** 2)))
            cover.setdefault(kind, []).append(np.mean(np.abs(y[te] - mu) <= 1.645 * np.sqrt(var_obs)))
    assert np.mean(ratio["still"]) < 1.12  # measured 1.00-1.13
    assert np.mean(ratio["moving"]) > 1.2  # measured 1.25-1.50
    assert min(np.mean(v) for v in cover.values()) > 0.8


def test_empirical_variogram_by_hand_and_against_the_model():
    P = np.array([[0.0, 0, 0], [1.0, 0, 0], [0.0, 0, 1]])
    y = np.array([0.0, 2.0, 1.0])
    rows = {(r[0], r[2]): r for r in variogram(P, y, [0.0, 0.5, 1.5], [0.0, 1.0])}
    assert rows[(0.5, 0.0)][3:] == (1, 2.0)  # 0.5 (0 - 2)^2
    assert rows[(0.0, 1.0)][3:] == (1, 0.5)
    assert rows[(0.5, 1.0)][3:] == (1, 0.5)  # (1, 0, 0) and (0, 0, 1): distance 1, lag 1
    m = {"params": np.array([1.0, 1.0, 1.0, 0.5]), "space": "exponential", "time": "exponential"}
    assert model_variogram(m, 0.0, 0.0) == pytest.approx(0.5)  # the nugget at zero lag
    assert model_variogram(m, 1e9, 0.0) == pytest.approx(1.5)


def test_the_command_line_runs_on_a_small_table(tmp_path, capsys, monkeypatch):
    import duckdb

    import st_kriging

    d = simulate("separable", 12, 10, seed=3)
    rows = [(f"L{k}", float(t), *d["coords"][k], float(v)) for k, t, v in zip(d["loc"], d["t"], d["y"])]
    path = str(tmp_path / "st.parquet")
    duckdb.sql("create table st (loc varchar, time double, x double, y double, value double)")
    duckdb.executemany("insert into st values (?, ?, ?, ?, ?)", rows)
    duckdb.sql(f"copy st to '{path}'")
    monkeypatch.setattr("sys.argv", ["st_kriging.py", path, "loc", "time", "x", "y", "value", "--cutoff", "6",
                                     "--time", "gaussian"])
    st_kriging.main()
    out = capsys.readouterr().out
    assert "rows 120" in out and "used 120" in out
    for kind in ("future_known", "new_location", "future_new"):
        assert f"{kind}: RMSE time" in out  # the default mean structure


def test_removing_the_location_effects_first_leaves_their_error_out_of_the_interval_at_new_places():
    # st_model's additive world: a spatial field of location levels plus a common AR(1) in time. At held-out
    # locations, "additive" fills a(s) by inverse distance and kriges what is left: the interval ignores the
    # error of a(s) (measured coverage 0.55-0.83). "time" leaves the levels to the spatial covariance and covers
    # (0.81-0.94) with about the same error.
    from st_kriging import detrend_and_krige

    cover = {"additive": [], "time": []}
    for s in range(3):
        d = simulate("additive", n_loc=40, n_t=15, seed=s)
        test = np.isin(d["loc"], np.arange(8))
        for how in cover:
            pred, var_obs, _, _ = detrend_and_krige(d["loc"], d["t"], d["y"], d["coords"], ~test, test, how)
            cover[how].append(np.mean(np.abs(d["y"][test] - pred) <= 1.645 * np.sqrt(var_obs)))
    assert np.mean(cover["additive"]) < 0.75
    assert np.mean(cover["time"]) > 0.82

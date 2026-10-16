"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyproj --with pyarrow --with pykrige --with pytest pytest test_interpolate_points_crosscheck.py

Ordinary and universal kriging against PyKrige (1.7.3) with the same variogram, every observation used (k = n).
PyKrige writes the exponential model as psill (1 - exp(-3 h / range)) + nugget: its range is three times ours.
Its universal kriging with drift_terms=["regional_linear"] is a drift in x and y, as here.
"""

import numpy as np
import pytest

from interpolate_points import Obs, predict

pk = pytest.importorskip("pykrige")


def _data(seed=0, n=60):
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, 10000, (n, 2))
    v = 0.0004 * xy[:, 0] - 0.0002 * xy[:, 1] + np.sin(xy[:, 0] / 1500) + 0.2 * rng.normal(size=n)
    q = np.r_[rng.uniform(0, 10000, (20, 2)), [[15000.0, 5000.0], [-3000.0, 12000.0]]]  # two outside
    return xy, v, q


@pytest.mark.parametrize("method", ["kriging", "universal"])
@pytest.mark.parametrize("nugget", [0.0, 0.05])
def test_predictions_and_variances_match_pykrige(method, nugget):
    from pykrige.ok import OrdinaryKriging
    from pykrige.uk import UniversalKriging

    xy, v, q = _data()
    sill, rng = 0.6, 1800.0
    ours = predict(Obs(xy, v), q, method, k=len(v), variogram=("exponential", nugget, sill, rng))
    params = {"psill": sill - nugget, "range": 3 * rng, "nugget": nugget}
    if method == "kriging":
        ref = OrdinaryKriging(xy[:, 0], xy[:, 1], v, variogram_model="exponential", variogram_parameters=params)
    else:
        ref = UniversalKriging(xy[:, 0], xy[:, 1], v, variogram_model="exponential", variogram_parameters=params,
                               drift_terms=["regional_linear"])
    z, ss = ref.execute("points", q[:, 0], q[:, 1])
    np.testing.assert_allclose(ours["prediction"], np.asarray(z), atol=1e-8)
    np.testing.assert_allclose(ours["kriging_sd"] ** 2, np.asarray(ss), atol=1e-8)


@pytest.mark.parametrize("angle,ratio", [(30.0, 3.0), (120.0, 2.0)])
def test_anisotropic_kriging_matches_pykrige(angle, ratio):
    from pykrige.ok import OrdinaryKriging

    xy, v, q = _data(seed=2)
    ours = predict(Obs(xy, v), q, "kriging", k=len(v), variogram=("exponential", 0.02, 0.6, 1800.0),
                   anisotropy=(angle, ratio))
    ref = OrdinaryKriging(xy[:, 0], xy[:, 1], v, variogram_model="exponential",
                          variogram_parameters={"psill": 0.58, "range": 5400.0, "nugget": 0.02},
                          anisotropy_scaling=ratio, anisotropy_angle=angle)
    z, ss = ref.execute("points", q[:, 0], q[:, 1])
    np.testing.assert_allclose(ours["prediction"], np.asarray(z), atol=1e-8)
    np.testing.assert_allclose(ours["kriging_sd"] ** 2, np.asarray(ss), atol=1e-8)

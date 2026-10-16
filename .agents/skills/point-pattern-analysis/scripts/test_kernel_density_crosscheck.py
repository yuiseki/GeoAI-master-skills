"""uvx --with numpy --with scipy --with scikit-learn --with pytest pytest test_kernel_density_crosscheck.py

intensity against scikit-learn's KernelDensity (Gaussian kernel, Euclidean distance): our intensity is the number
of points times its density. The leave-one-out log-likelihood of lcv_bandwidth against the same sums computed with
KernelDensity fitted on every point but one.
"""

import numpy as np
import pytest
from sklearn.neighbors import KernelDensity

from kernel_density import intensity, lcv_bandwidth


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("h", [0.3, 1.0, 4.0])
def test_intensity_matches_sklearn(seed, h):
    rng = np.random.default_rng(seed)
    x, y = rng.normal(size=200), rng.normal(size=200) * 2
    gx, gy = rng.uniform(-5, 5, 300), rng.uniform(-5, 5, 300)
    kd = KernelDensity(kernel="gaussian", bandwidth=h).fit(np.c_[x, y])
    ref = len(x) * np.exp(kd.score_samples(np.c_[gx, gy]))
    assert intensity(x, y, gx, gy, h) == pytest.approx(ref, rel=1e-9)


def test_leave_one_out_likelihood_matches_sklearn():
    rng = np.random.default_rng(5)
    x, y = rng.normal(size=60), rng.normal(size=60)
    h = 0.7
    ref = sum(KernelDensity(kernel="gaussian", bandwidth=h).fit(np.delete(np.c_[x, y], i, 0))
              .score_samples(np.c_[x[i], y[i]])[0] for i in range(60))
    assert lcv_bandwidth(x, y, [h])["scores"][0][1] == pytest.approx(ref, rel=1e-9)

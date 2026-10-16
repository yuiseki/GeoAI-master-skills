"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pointpats --with pytest pytest test_cox_crosscheck.py

K without edge correction against PySAL's pointpats (2.6.0), whose k() has no edge correction yet. pointpats
divides by the area of the points' bounding box (not the window) and by n^2 (not n (n - 1)); with those two
factors the values must agree. The translation correction, the Thomas formula and the LGCP integral have no
Python counterpart here; they are checked against simulations in test_cox.py.
"""

import numpy as np
import pytest

from cox import k_function, simulate_lgcp, simulate_thomas

distance_statistics = pytest.importorskip("pointpats.distance_statistics")
W = (0.0, 1.0, 0.0, 1.0)


@pytest.mark.parametrize("kind", ["thomas", "lgcp", "poisson"])
def test_k_without_edge_correction_matches_pointpats(kind):
    rng = np.random.default_rng(1)
    if kind == "thomas":
        x, y = simulate_thomas(25, 10, 0.03, W, seed=1)
    elif kind == "lgcp":
        x, y = simulate_lgcp(np.log(200) - 0.5, 1.0, 0.08, W, seed=1)
    else:
        x, y = rng.random(150), rng.random(150)
    rs = np.linspace(0.01, 0.2, 20)
    _, theirs = distance_statistics.k(np.c_[x, y], support=rs)
    n = len(x)
    ours = k_function(x, y, W, rs, "none") * (np.ptp(x) * np.ptp(y)) * (n - 1) / n
    np.testing.assert_allclose(ours, theirs, rtol=1e-10)

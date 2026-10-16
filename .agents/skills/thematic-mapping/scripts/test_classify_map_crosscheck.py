"""uvx --with numpy --with duckdb --with shapely --with matplotlib --with mapclassify --with pytest pytest test_classify_map_crosscheck.py

breaks() against mapclassify: EqualInterval, Quantiles and FisherJenks upper bounds, and the class of each
value (mapclassify's bins are upper-inclusive, as ours).
"""

import mapclassify
import numpy as np
import pytest

from classify_map import assign, breaks


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("k", [3, 5, 7])
@pytest.mark.parametrize("method,cls", [("equal", mapclassify.EqualInterval), ("quantile", mapclassify.Quantiles),
                                        ("jenks", mapclassify.FisherJenks)])
def test_against_mapclassify(seed, k, method, cls):
    x = np.random.default_rng(seed).lognormal(0, 1, 300)
    ref = cls(x, k=k)
    ours = breaks(x, method, k)
    assert ours[1:] == pytest.approx(ref.bins, rel=1e-9)
    assert (assign(x, ours) == ref.yb).all()

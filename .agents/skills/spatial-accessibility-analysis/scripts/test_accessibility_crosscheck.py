"""uvx --with numpy --with duckdb --with pandas --with access --with pytest pytest test_accessibility_crosscheck.py

fca() and hansen() against PySAL's access package (1.1.10): two_stage_fca, enhanced_two_stage_fca with a
step function, weighted_catchment with a power gravity. access's gaussian weight is not normalised to 0 at
the catchment edge (it is exp(-d^2 / 2 sigma^2)); ours is, so the gaussian is not compared.
"""

import numpy as np
import pandas as pd
import pytest
from access import Access, weights

from accessibility import fca, hansen, weight


def _world(seed, n=30, m=6, integer=False):
    rng = np.random.default_rng(seed)
    P, S = rng.integers(1, 500, n).astype(float), rng.uniform(1, 20, m)
    C = rng.integers(0, 30, (n, m)).astype(float) if integer else rng.uniform(0, 30, (n, m))
    dem = pd.DataFrame({"P": P}, index=pd.Index(range(n), name="o"))
    sup = pd.DataFrame({"S": S}, index=pd.Index(range(m), name="f"))
    cost = pd.DataFrame([(i, j, C[i, j]) for i in range(n) for j in range(m)], columns=["o", "f", "c"])
    acc = Access(demand_df=dem, demand_value="P", supply_df=sup, supply_value="S", cost_df=cost, cost_origin="o",
                 cost_dest="f", cost_name="c")
    return P, S, C, acc, n


def _col(df, n):
    return df.iloc[:, -1].reindex(range(n)).fillna(0).to_numpy()


@pytest.mark.parametrize("seed", range(4))
def test_two_step_matches_access(seed):
    # Integer costs put many pairs exactly on the catchment edge: both count them as inside.
    P, S, C, acc, n = _world(seed, integer=seed % 2 == 0)
    ref = _col(acc.two_stage_fca(max_cost=12), n)
    assert np.allclose(fca(P, S, C, lambda d: weight(d, "binary", 12))["access"], ref, rtol=1e-12, atol=1e-15)


@pytest.mark.parametrize("seed", range(4))
def test_enhanced_two_step_with_steps_matches_access(seed):
    P, S, C, acc, n = _world(seed, integer=seed % 2 == 0)
    ref = _col(acc.enhanced_two_stage_fca(max_cost=12, weight_fn=weights.step_fn({6: 1.0, 12: 0.5})), n)
    ours = fca(P, S, C, lambda d: weight(d, "steps", 12, steps=[(6, 1.0), (12, 0.5)]))["access"]
    assert np.allclose(ours, ref, rtol=1e-12, atol=1e-15)


@pytest.mark.parametrize("seed", range(4))
def test_hansen_matches_access_weighted_catchment(seed):
    P, S, C, acc, n = _world(seed)
    ref = _col(acc.weighted_catchment(weight_fn=weights.gravity(scale=1, alpha=-1)), n)
    assert np.allclose(hansen(S, C, lambda d: weight(d, "power", None, beta=1.0)), ref, rtol=1e-12)

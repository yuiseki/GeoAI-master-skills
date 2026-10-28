import numpy as np
import pandas as pd

import analysis as an


def test_delta_t_is_last_summer_minus_the_one_before():
    s = pd.DataFrame({"region": "a", "year": [2018, 2019, 2020, 2021], "summer_tmax_c": [24.0, 25.0, 23.5, 26.0]})
    d = an.with_delta_t(s)
    assert d.set_index("year").loc[2020, "dT"] == 1.0  # 2019 - 2018
    assert d.set_index("year").loc[2021, "dT"] == -1.5  # 2020 - 2019
    assert np.isnan(d.set_index("year").loc[2018, "dT"])


def test_demean_is_within_region():
    df = pd.DataFrame({"region": ["a", "a", "b", "b"], "autumn": [0, 99, 9, 9]})
    y = an.demeaned_log(df, "autumn")
    assert np.allclose(y[:2], [-np.log(100) / 2, np.log(100) / 2]) and np.allclose(y[2:], 0)


def test_within_region_permutation_finds_a_planted_relation_and_not_a_null_one():
    rng = np.random.default_rng(0)
    regions = np.repeat(["a", "b", "c", "d"], 8)
    x = rng.normal(size=32)
    y = -x + rng.normal(0, 0.3, 32)
    rho, p = an.permutation_spearman(x, y, regions, n=2000, seed=0, alternative="less")
    assert rho < -0.7 and p < 0.01
    rho, p = an.permutation_spearman(x, rng.normal(size=32), regions, n=2000, seed=0, alternative="less")
    assert p > 0.05


def test_permutation_keeps_each_region_values():
    regions = np.array(["a", "a", "b", "b"])
    y = np.array([1.0, 2.0, 10.0, 20.0])
    for s in range(5):
        yp = an.permute_within(y, regions, np.random.default_rng(s))
        assert sorted(yp[:2]) == [1.0, 2.0] and sorted(yp[2:]) == [10.0, 20.0]

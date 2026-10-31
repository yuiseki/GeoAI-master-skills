"""Known-answer tests for the input alignment."""

import numpy as np
import pytest

import align_inputs as al


def test_pc1_recovers_a_shared_factor_with_the_requested_sign():
    rng = np.random.default_rng(0)
    f = rng.normal(size=2000)
    Z = np.column_stack([-f + rng.normal(0, 0.1, 2000), f + rng.normal(0, 0.1, 2000), rng.normal(size=2000)])
    s, load, share = al.pc1(Z, sign_col=1)
    assert load[1] > 0 and load[0] < 0 and abs(load[2]) < 0.1
    assert np.corrcoef(s, f)[0, 1] > 0.99
    assert s.mean() == pytest.approx(0, abs=1e-9) and s.std() == pytest.approx(1)
    assert 0.6 < share < 0.7


def test_standardise_centres_and_scales_each_column():
    X = np.array([[1.0, 10.0], [3.0, 30.0]])
    assert al.standardise(X).tolist() == [[-1.0, -1.0], [1.0, 1.0]]

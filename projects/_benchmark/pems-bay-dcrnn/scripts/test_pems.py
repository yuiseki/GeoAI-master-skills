"""uvx --python 3.12 --with numpy --with torch --with pytest pytest -q test_pems.py"""

import numpy as np
import pytest

from pems import (adjacency, historical_average, make_xy, masked_metrics, random_walk, split_counts, time_in_day,
                  window_starts)


def test_windows_and_split_follow_the_author_script():
    n_time = 100
    starts = window_starts(n_time, 12, 12)
    assert starts[0] == 11 and starts[-1] == n_time - 12 - 1 and len(starts) == n_time - 23
    tr, va, te = split_counts(len(starts))
    assert tr == round(0.7 * len(starts)) and te == round(0.2 * len(starts)) and tr + va + te == len(starts)


def test_make_xy_offsets():
    v = np.arange(40, dtype=float).reshape(20, 2)          # time x node
    tod = np.linspace(0, 1, 20, endpoint=False)
    x, y = make_xy(v, tod, np.array([11]), 12, 3)
    assert x.shape == (1, 12, 2, 2) and y.shape == (1, 3, 2)
    assert x[0, -1, 0, 0] == v[11, 0] and x[0, 0, 0, 0] == v[0, 0] and y[0, 0, 1] == v[12, 1]
    assert x[0, -1, 1, 1] == tod[11]


def test_time_in_day():
    t = np.array([0, 6 * 3600, 23 * 3600 + 55 * 60], dtype="int64") * 10**9
    assert np.allclose(time_in_day(t), [0, 0.25, (23 * 60 + 55) / 1440])


def test_adjacency_uses_the_gaussian_kernel_and_the_cutoff():
    ids = [1, 2, 3]
    rows = [(1, 1, 0.0), (1, 2, 1.0), (2, 3, 10.0)]
    a = adjacency(rows, ids, k=0.1)
    d = np.array([0.0, 1.0, 10.0])
    std = d.std()
    assert a[0, 0] == 1.0 and a[0, 1] == pytest.approx(np.exp(-(1 / std) ** 2))
    assert a[1, 0] == 0.0                                   # directed: no distance given from 2 to 1
    assert a[1, 2] == (np.exp(-(10 / std) ** 2) if np.exp(-(10 / std) ** 2) >= 0.1 else 0.0)
    assert a[2, 2] == 0.0                                   # self distances only where given


def test_random_walk_rows_sum_to_one_or_zero():
    a = np.array([[0, 2.0, 2.0], [1.0, 0, 0], [0, 0, 0]])
    p = random_walk(a)
    assert np.allclose(p.sum(1), [1, 1, 0]) and p[0, 1] == pytest.approx(0.5)


def test_masked_metrics_leave_out_zeros():
    y = np.array([0.0, 50.0, 60.0])
    p = np.array([10.0, 55.0, 57.0])
    m = masked_metrics(p, y)
    assert m["mae"] == pytest.approx(4.0) and m["rmse"] == pytest.approx(np.sqrt((25 + 9) / 2))
    assert m["mape"] == pytest.approx((5 / 50 + 3 / 60) / 2)


def test_historical_average_recovers_a_weekly_pattern():
    week = 7 * 288
    pattern = np.sin(np.arange(week) / 50.0) * 10 + 60
    v = np.tile(pattern, 6)[:, None].repeat(3, 1)
    target = np.array([5 * week + 100, 5 * week + 2000])
    ha = historical_average(v, target, weeks=4)
    assert np.allclose(ha, v[target])
    v2 = v.copy()
    v2[4 * week + 100, 0] = 0.0                              # a missing reading is left out of the average
    assert historical_average(v2, target[:1], weeks=4)[0, 0] == pytest.approx(v[target[0], 0])


def test_diffusion_reaches_k_hops_and_k0_sees_no_neighbour():
    torch = pytest.importorskip("torch")
    from model import DiffusionConv
    n = 5
    a = np.zeros((n, n))
    for i in range(n - 1):
        a[i, i + 1] = 1.0                                     # a chain 0 -> 1 -> 2 -> 3 -> 4
    sup = [torch.tensor(random_walk(a).T, dtype=torch.float32), torch.tensor(random_walk(a.T).T, dtype=torch.float32)]
    for k, reach in ((0, {0}), (1, {0, 1}), (2, {0, 1, 2})):
        torch.manual_seed(0)
        conv = DiffusionConv(sup, in_dim=1, out_dim=4, k=k)
        x = torch.zeros(1, n, 1)
        base = conv(x)
        x[0, 0, 0] = 1.0                                     # poke node 0
        changed = {i for i in range(n) if not torch.allclose(conv(x)[0, i], base[0, i])}
        assert changed == reach, (k, changed)


def test_dcrnn_shapes_and_teacher_forcing():
    torch = pytest.importorskip("torch")
    from model import DCRNN
    a = np.eye(4) + np.eye(4, k=1)
    sup = [torch.tensor(random_walk(a).T, dtype=torch.float32), torch.tensor(random_walk(a.T).T, dtype=torch.float32)]
    m = DCRNN(sup, num_nodes=4, in_dim=2, units=8, layers=2, k=2, horizon=3)
    x, y = torch.randn(5, 12, 4, 2), torch.randn(5, 3, 4)
    assert m(x).shape == (5, 3, 4)
    assert m(x, y, teacher_prob=1.0).shape == (5, 3, 4)

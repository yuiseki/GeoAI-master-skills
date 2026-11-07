"""uvx --python 3.12 --with numpy --with torch==2.14.1 --with pytest pytest -q test_dcrnn.py"""

import numpy as np
import pytest
import torch

from dcrnn import DCRNN, DiffusionConv, masked_mae, supports_to_torch, teacher_prob
from graph_build import diffusion_supports


def chain(n):
    a = np.zeros((n, n))
    for i in range(n - 1):
        a[i, i + 1] = 1.0                                     # 0 -> 1 -> ... -> n-1
    return a


def test_diffusion_reaches_k_hops_and_k0_sees_no_neighbour():
    sup = supports_to_torch(diffusion_supports(chain(5)))
    for k, reach in ((0, {0}), (1, {0, 1}), (2, {0, 1, 2})):
        torch.manual_seed(0)
        conv = DiffusionConv(sup, in_dim=1, out_dim=4, k=k)
        x = torch.zeros(1, 5, 1)
        base = conv(x)
        x[0, 0, 0] = 1.0
        changed = {i for i in range(5) if not torch.allclose(conv(x)[0, i], base[0, i])}
        assert changed == reach, (k, changed)


def test_dcrnn_shapes_teacher_forcing_and_eval_ignores_the_truth():
    sup = supports_to_torch(diffusion_supports(np.eye(4) + np.eye(4, k=1)))
    torch.manual_seed(0)
    m = DCRNN(sup, num_nodes=4, in_dim=2, units=8, layers=2, k=2, horizon=3)
    x, y = torch.randn(5, 12, 4, 2), torch.randn(5, 3, 4)
    assert m(x).shape == (5, 3, 4)
    assert m(x, y, teacher_prob=1.0).shape == (5, 3, 4)
    m.eval()
    with torch.no_grad():
        assert torch.allclose(m(x, y, teacher_prob=1.0), m(x))


def test_k0_output_of_a_node_does_not_depend_on_other_nodes():
    sup = supports_to_torch(diffusion_supports(chain(4)))
    torch.manual_seed(0)
    m = DCRNN(sup, num_nodes=4, in_dim=2, units=8, layers=2, k=0, horizon=2).eval()
    x = torch.randn(1, 12, 4, 2)
    x2 = x.clone()
    x2[:, :, 1:] += 5.0
    with torch.no_grad():
        assert torch.allclose(m(x)[..., 0], m(x2)[..., 0])


def test_teacher_prob_and_masked_mae():
    assert teacher_prob(0) == pytest.approx(2000 / 2001)
    assert teacher_prob(40000) < 1e-5
    p, t = torch.tensor([1.0, 5.0, 9.0]), torch.tensor([0.0, 4.0, 6.0])
    assert masked_mae(p, t).item() == pytest.approx(2.0)

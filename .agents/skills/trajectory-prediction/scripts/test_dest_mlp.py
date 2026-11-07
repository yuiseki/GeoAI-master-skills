"""uvx --python 3.12 --with numpy --with torch --with scikit-learn --with pytest pytest -q test_dest_mlp.py"""

import math

import numpy as np
import pytest
import torch

from dest_mlp import DestMLP, destination_clusters, equirect_loss


def test_output_stays_in_the_hull_of_the_centres():
    centres = np.array([[41.1, -8.6], [41.2, -8.5], [41.15, -8.7]])
    m = DestMLP(centres, n_points=10, emb_sizes={"taxi": 5}, emb_dim=4, hidden=8)
    y = m(torch.randn(6, 20) * 10, {"taxi": torch.tensor([0, 1, 2, 3, 4, 0])}).detach().numpy()
    assert y.shape == (6, 2)
    assert (y[:, 0] >= 41.1 - 1e-6).all() and (y[:, 0] <= 41.2 + 1e-6).all()
    assert DestMLP(centres, n_points=10, emb_sizes={}, hidden=8)(torch.randn(6, 20), {}).shape == (6, 2)


def test_loss_is_zero_at_the_target_and_one_degree_of_latitude_is_111_km():
    p = torch.tensor([[41.0, -8.6], [42.0, -8.6]], dtype=torch.float64)
    t = torch.tensor([[41.0, -8.6], [41.0, -8.6]], dtype=torch.float64)
    v = equirect_loss(p, t, reduce=False).numpy()
    assert v[0] == pytest.approx(0, abs=1e-3) and v[1] == pytest.approx(6371 * math.pi / 180, rel=1e-9)


def test_clusters_find_separated_blobs():
    rng = np.random.default_rng(0)
    pts = np.concatenate([rng.normal(c, 0.0002, (300, 2)) for c in ([41.15, -8.61], [41.18, -8.58])])
    c = destination_clusters(pts, bandwidth=0.001, n_jobs=1)
    assert len(c) == 2


def test_it_learns_a_destination_that_depends_on_the_prefix():
    torch.manual_seed(0)
    centres = np.array([[41.10, -8.60], [41.20, -8.60]])
    x = torch.randn(400, 4)
    y = torch.where((x[:, :1] > 0), torch.tensor([41.20, -8.60]), torch.tensor([41.10, -8.60]))
    m = DestMLP(centres, n_points=2, emb_sizes={}, hidden=16)
    opt = torch.optim.SGD(m.parameters(), lr=0.01, momentum=0.9)
    first = equirect_loss(m(x, {}), y).item()
    for _ in range(300):
        loss = equirect_loss(m(x, {}), y)
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert loss.item() < first / 3

"""The destination MLP of de Brebisson et al. (2015, section 2), tested in test_dest_mlp.py.

  destination_clusters   mean-shift centres of the training destinations (bandwidth in degrees; 0.001 in the paper)
  DestMLP                first and last k points (standardised) + metadata embeddings -> one hidden ReLU layer ->
                         softmax over the cluster centres -> their weighted mean. The prediction stays inside the
                         convex hull of the centres
  equirect_loss          the training loss in km

Settings that reproduced the paper on Porto: k = 5, embeddings of 10, 500 hidden units, SGD momentum 0.9, learning
rate 0.01, batch 200, the best validation of every 10,000 steps over 300,000 steps.
"""

import math

import numpy as np
import torch
from torch import nn

R = 6371.0


def destination_clusters(points, bandwidth=0.001, min_bin_freq=5, n_jobs=4):
    from sklearn.cluster import MeanShift
    return MeanShift(bandwidth=bandwidth, bin_seeding=True, min_bin_freq=min_bin_freq, n_jobs=n_jobs).fit(
        np.asarray(points)).cluster_centers_


class DestMLP(nn.Module):
    def __init__(self, centres, n_points, emb_sizes, emb_dim=10, hidden=500):
        super().__init__()
        self.register_buffer("centres", torch.as_tensor(np.asarray(centres), dtype=torch.float32))
        self.emb = nn.ModuleDict({k: nn.Embedding(v, emb_dim) for k, v in emb_sizes.items()})
        for e in self.emb.values():
            nn.init.normal_(e.weight, std=0.01)
        self.hidden = nn.Linear(2 * n_points + emb_dim * len(emb_sizes), hidden)
        self.out = nn.Linear(hidden, len(self.centres))
        for layer in (self.hidden, self.out):
            nn.init.normal_(layer.weight, std=0.1)
            nn.init.constant_(layer.bias, 0.01)

    def forward(self, x, meta):
        h = torch.relu(self.hidden(torch.cat([x] + [self.emb[k](meta[k]) for k in self.emb], 1)))
        return torch.softmax(self.out(h), 1) @ self.centres


def equirect_loss(pred, target, reduce=True):
    rad = math.pi / 180
    lat1, lon1, lat2, lon2 = pred[:, 0] * rad, pred[:, 1] * rad, target[:, 0] * rad, target[:, 1] * rad
    x = (lon2 - lon1) * torch.cos((lat1 + lat2) / 2)
    d = R * torch.sqrt(x * x + (lat2 - lat1) ** 2 + 1e-16)    # keeps the gradient finite at 0; adds < 0.1 m
    return d.mean() if reduce else d

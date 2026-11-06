"""The winning model of de Brebisson et al. (2015), section 2: an MLP over the first and last k points of the prefix and
embeddings of the metadata, whose softmax weights average fixed destination cluster centres."""

import math

import torch
from torch import nn

R = 6371.0


class DestMLP(nn.Module):
    def __init__(self, centres, n_points, emb_sizes, emb_dim=10, hidden=500):
        super().__init__()
        self.register_buffer("centres", torch.as_tensor(centres, dtype=torch.float32))
        self.emb = nn.ModuleDict({k: nn.Embedding(v, emb_dim) for k, v in emb_sizes.items()})
        for e in self.emb.values():
            nn.init.normal_(e.weight, std=0.01)
        self.hidden = nn.Linear(2 * n_points + emb_dim * len(emb_sizes), hidden)
        self.out = nn.Linear(hidden, len(centres))
        for l in (self.hidden, self.out):
            nn.init.normal_(l.weight, std=0.1)
            nn.init.constant_(l.bias, 0.01)

    def forward(self, x, meta):
        parts = [x] + [self.emb[k](meta[k]) for k in self.emb]
        h = torch.relu(self.hidden(torch.cat(parts, 1)))
        p = torch.softmax(self.out(h), 1)
        return p @ self.centres


def equirect_loss(pred, target, reduce=True):
    rad = math.pi / 180
    lat1, lon1, lat2, lon2 = pred[:, 0] * rad, pred[:, 1] * rad, target[:, 0] * rad, target[:, 1] * rad
    x = (lon2 - lon1) * torch.cos((lat1 + lat2) / 2)
    d = R * torch.sqrt(x * x + (lat2 - lat1) ** 2 + 1e-16)   # keeps the gradient finite at 0; adds < 1 m
    return d.mean() if reduce else d

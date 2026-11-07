"""DCRNN (Li et al. 2018) in PyTorch: diffusion convolution inside a GRU, an encoder over the 12 inputs and a decoder
over the horizon with scheduled sampling. k = 0 drops the graph (every sensor its own GRU with shared weights).

  DiffusionConv(supports, in_dim, out_dim, k)   [x, S1 x, T2(S1) x, ..., S2 x, ...] -> linear; T2 = 2 S T1 - T0
  DCGRUCell                                     GRU gates and candidate from diffusion convolutions
  DCRNN(supports, num_nodes, in_dim, units, layers, k, horizon)
     forward(x, y=None, teacher_prob=0)         x (b, 12, n, in_dim) -> (b, horizon, n); y: the truth (scaled)
"""

import torch
from torch import nn


class DiffusionConv(nn.Module):
    def __init__(self, supports, in_dim, out_dim, k, bias_start=0.0):
        super().__init__()
        self.supports, self.k = supports, k
        n_mat = len(supports) * k + 1
        self.lin = nn.Linear(in_dim * n_mat, out_dim)
        nn.init.xavier_normal_(self.lin.weight)
        nn.init.constant_(self.lin.bias, bias_start)

    def forward(self, x):                      # x (b, n, d)
        out = [x]
        if self.k > 0:
            for s in self.supports:
                x1 = torch.einsum("ij,bjd->bid", s, x)
                out.append(x1)
                x0 = x
                for _ in range(2, self.k + 1):
                    x2 = 2 * torch.einsum("ij,bjd->bid", s, x1) - x0
                    out.append(x2)
                    x0, x1 = x1, x2
        return self.lin(torch.cat(out, -1))


class DCGRUCell(nn.Module):
    def __init__(self, supports, in_dim, units, k):
        super().__init__()
        self.units = units
        self.gates = DiffusionConv(supports, in_dim + units, 2 * units, k, bias_start=1.0)
        self.cand = DiffusionConv(supports, in_dim + units, units, k)

    def forward(self, x, h):
        ru = torch.sigmoid(self.gates(torch.cat([x, h], -1)))
        r, u = ru.split(self.units, -1)
        c = torch.tanh(self.cand(torch.cat([x, r * h], -1)))
        return u * h + (1 - u) * c


class DCRNN(nn.Module):
    def __init__(self, supports, num_nodes, in_dim=2, units=64, layers=2, k=2, horizon=12):
        super().__init__()
        self.n, self.units, self.horizon = num_nodes, units, horizon
        for i, s in enumerate(supports):
            self.register_buffer(f"s{i}", s)
        sup = [getattr(self, f"s{i}") for i in range(len(supports))]
        self.enc = nn.ModuleList([DCGRUCell(sup, in_dim if i == 0 else units, units, k) for i in range(layers)])
        self.dec = nn.ModuleList([DCGRUCell(sup, 1 if i == 0 else units, units, k) for i in range(layers)])
        self.proj = nn.Linear(units, 1)
        self._sup = sup

    def _refresh(self):                        # keep the cells pointing at the buffers after .to(device)
        sup = [getattr(self, f"s{i}") for i in range(len(self._sup))]
        for cell in list(self.enc) + list(self.dec):
            cell.gates.supports = sup
            cell.cand.supports = sup

    def forward(self, x, y=None, teacher_prob=0.0):
        self._refresh()
        b = x.shape[0]
        h = [x.new_zeros(b, self.n, self.units) for _ in self.enc]
        for t in range(x.shape[1]):
            inp = x[:, t]
            for i, cell in enumerate(self.enc):
                h[i] = cell(inp, h[i])
                inp = h[i]
        go = x.new_zeros(b, self.n, 1)
        outs = []
        for t in range(self.horizon):
            inp = go
            for i, cell in enumerate(self.dec):
                h[i] = cell(inp, h[i])
                inp = h[i]
            o = self.proj(inp)                   # (b, n, 1)
            outs.append(o[..., 0])
            if y is not None and self.training and teacher_prob > 0 and torch.rand(()) < teacher_prob:
                go = y[:, t, :, None]
            else:
                go = o
        return torch.stack(outs, 1)

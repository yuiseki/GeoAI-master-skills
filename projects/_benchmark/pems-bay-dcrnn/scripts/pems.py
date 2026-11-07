"""Data, graph, metrics and the historical average of EXPERIMENT_PLAN.md, tested in test_pems.py.
Follows scripts/generate_training_data.py and scripts/gen_adj_mx.py of the DCRNN repository.

  read_h5             the pandas HDF5 of the authors, read with h5py (values, times in ns, sensor ids); no pickle
  window_starts       sample t uses times t-11..t as input and t+1..t+12 as output
  split_counts        70% train, 20% test (rounded), the rest validation, in time order
  make_xy             x (batch, 12, nodes, 2) = speed and time in day; y (batch, horizon, nodes)
  adjacency           W_ij = exp(-(d_ij / sd)^2) for the given directed distances, 0 below k (0.1)
  random_walk         D_out^-1 W (rows of sinks stay 0)
  masked_metrics      MAE, RMSE, MAPE leaving out the points whose truth is 0 (missing)
  historical_average  the mean of the same time of the week over the previous `weeks` weeks, zeros left out
"""

import numpy as np

STEPS_PER_DAY = 288
WEEK = 7 * STEPS_PER_DAY


def read_h5(path):
    import h5py
    with h5py.File(path, "r") as h:
        g = h[list(h.keys())[0]]
        return g["block0_values"][:], g["axis1"][:].astype("int64"), g["axis0"][:]


def time_in_day(t_ns):
    day = 86400 * 10**9
    return (np.asarray(t_ns, dtype="int64") % day) / day


def window_starts(n_time, n_in=12, n_out=12):
    return np.arange(n_in - 1, n_time - n_out)


def split_counts(n):
    test = round(n * 0.2)
    train = round(n * 0.7)
    return train, n - train - test, test


def make_xy(values, tod, starts, n_in=12, horizon=12):
    xi = starts[:, None] + np.arange(-(n_in - 1), 1)[None, :]
    yi = starts[:, None] + np.arange(1, horizon + 1)[None, :]
    speed = values[xi]                                        # (b, n_in, nodes)
    t = np.broadcast_to(tod[xi][:, :, None], speed.shape)
    return np.stack([speed, t], -1), values[yi]


def adjacency(rows, ids, k=0.1):
    pos = {int(s): i for i, s in enumerate(ids)}
    d = np.full((len(ids), len(ids)), np.inf)
    for a, b, dist in rows:
        if int(a) in pos and int(b) in pos:
            d[pos[int(a)], pos[int(b)]] = float(dist)
    sd = d[np.isfinite(d)].std()
    w = np.exp(-np.square(d / sd))
    w[w < k] = 0.0
    return w


def random_walk(w):
    deg = w.sum(1)
    inv = np.where(deg > 0, 1.0 / np.where(deg > 0, deg, 1.0), 0.0)
    return inv[:, None] * w


def masked_metrics(pred, truth):
    ok = truth != 0
    e = pred[ok] - truth[ok]
    return dict(mae=float(np.abs(e).mean()), rmse=float(np.sqrt((e * e).mean())),
                mape=float((np.abs(e) / np.abs(truth[ok])).mean()))


def historical_average(values, target, weeks=4):
    idx = np.asarray(target)[:, None] - WEEK * np.arange(1, weeks + 1)[None, :]
    v = values[np.maximum(idx, 0)]                            # (b, weeks, nodes)
    ok = (idx[:, :, None] >= 0) & (v != 0)
    return np.where(ok, v, 0).sum(1) / np.maximum(ok.sum(1), 1)

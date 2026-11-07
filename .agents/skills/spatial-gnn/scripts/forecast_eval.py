"""Windows, splits, baselines and paired evaluation for forecasting values on a sensor graph.

Follows generate_training_data.py of the DCRNN repository. values is (time, nodes); 0 marks a missing reading.

  window_starts(n_time, n_in, n_out)   sample t uses times t-n_in+1..t as input and t+1..t+n_out as output
  split_counts(n)                       70% train, 20% test (rounded), the rest validation, in time order
  make_xy(values, tod, starts, ...)     x (b, n_in, nodes, 2) = value and time in day; y (b, horizon, nodes)
  time_in_day(t_ns)                     the fraction of the day of int64 nanoseconds
  last_value(values, starts)            the last input value as the forecast for every horizon
  historical_average(values, target, steps_per_week, weeks)
                                        mean of the same time of the week over the previous weeks, zeros left out
  masked_metrics(pred, truth)           MAE, RMSE, MAPE leaving out the points whose truth is 0
  paired_day_sums(a, b, truth, days)    per day, sum of |a - truth| - |b - truth| and the count of kept points
  day_sums(pred, truth, days)           per day, sum of |pred - truth| and the count (for one model's interval)
  boot_ratio(sums, counts)              95% interval of sum / count, drawing whole days with replacement
  share_of_gain(a, b, truth, mask)      the share of the total paired gain sum(|a|-|b|) that falls in mask
"""

import numpy as np


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
    v = values[xi]
    t = np.broadcast_to(tod[xi][:, :, None], v.shape)
    return np.stack([v, t], -1), values[yi]


def last_value(values, starts):
    return values[np.asarray(starts)]


def historical_average(values, target, steps_per_week=7 * 288, weeks=4):
    idx = np.asarray(target)[:, None] - steps_per_week * np.arange(1, weeks + 1)[None, :]
    v = values[np.maximum(idx, 0)]
    ok = (idx[:, :, None] >= 0) & (v != 0)
    return np.where(ok, v, 0).sum(1) / np.maximum(ok.sum(1), 1)


def masked_metrics(pred, truth):
    ok = truth != 0
    e = pred[ok] - truth[ok]
    return dict(mae=float(np.abs(e).mean()), rmse=float(np.sqrt((e * e).mean())),
                mape=float((np.abs(e) / np.abs(truth[ok])).mean()))


def _by_day(per_row, ok, days):
    u, inv = np.unique(days, return_inverse=True)
    return u, np.bincount(inv, per_row), np.bincount(inv, ok.reshape(len(days), -1).sum(1))


def day_sums(pred, truth, days):
    ok = truth != 0
    return _by_day((np.abs(pred - truth) * ok).reshape(len(days), -1).sum(1), ok, days)


def paired_day_sums(pred_a, pred_b, truth, days):
    ok = truth != 0
    d = (np.abs(pred_a - truth) - np.abs(pred_b - truth)) * ok
    return _by_day(d.reshape(len(days), -1).sum(1), ok, days)


def boot_ratio(sums, counts, reps=2000, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(counts), (reps, len(counts)))
    return tuple(np.percentile(sums[idx].sum(1) / counts[idx].sum(1), [2.5, 97.5]))


def share_of_gain(pred_a, pred_b, truth, mask):
    ok = truth != 0
    g = (np.abs(pred_a - truth) - np.abs(pred_b - truth)) * ok
    return float(g[mask & ok].sum() / g[ok].sum())

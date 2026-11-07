"""Pieces of EXPERIMENT_PLAN.md, tested in test_s1f11.py. Follows Train.ipynb of the Sen1Floods11 repository.

  preprocess          S1 dB (2, H, W) -> nan to 0, clip to [-50, 1], (x + 50) / 51, standardise with the hand-labeled
                      training mean and sd of the paper
  labels_to_target    LabelHand (-1 invalid, 0, 1) -> target with IGNORE for invalid
  chip_iou            water IoU of one chip, invalid pixels left out, (I + 1e-7) / (U + 1e-7) as in the notebook
  pooled_iou          water IoU over all pixels of all chips
  flood_permanent     (pred, target) pairs for flood water (permanent pixels left out) and permanent water
                      (water target only where JRC says permanent)
  tiles4, untile4     a 512 chip as four 256 tiles (top left, top right, bottom left, bottom right) and back
  random_crop_flip    a random 256 crop with random horizontal and vertical flips of image and label together
"""

import numpy as np

IGNORE = 255
MEAN = np.array([0.6851, 0.5235], dtype="float32")
SD = np.array([0.0820, 0.1102], dtype="float32")
EPS = 1e-7


def preprocess(x):
    x = np.nan_to_num(np.asarray(x, dtype="float32"), nan=0.0)
    x = (np.clip(x, -50, 1) + 50) / 51
    return (x - MEAN[:, None, None]) / SD[:, None, None]


def labels_to_target(lab):
    t = np.asarray(lab).astype("int64")
    t[t == -1] = IGNORE
    return t


def _iu(pred, target):
    ok = target != IGNORE
    p, t = np.asarray(pred)[ok] == 1, target[ok] == 1
    i = np.sum(p & t)
    return i, np.sum(p) + np.sum(t) - i


def chip_iou(pred, target):
    i, u = _iu(pred, np.asarray(target))
    return float((i + EPS) / (u + EPS))


def pooled_iou(preds, targets):
    iu = np.array([_iu(p, np.asarray(t)) for p, t in zip(preds, targets)])
    return float(iu[:, 0].sum() / iu[:, 1].sum())


def flood_permanent(pred, target, jrc):
    target, jrc = np.asarray(target), np.asarray(jrc)
    tf = np.where(jrc == 1, IGNORE, target)
    tp = np.where(target == IGNORE, IGNORE, ((target == 1) & (jrc == 1)).astype(target.dtype))
    return (np.asarray(pred), tf), (np.asarray(pred), tp)


def tiles4(a):
    return np.stack([a[..., :256, :256], a[..., :256, 256:], a[..., 256:, :256], a[..., 256:, 256:]])


def untile4(t):
    top = np.concatenate([t[0], t[1]], -1)
    bottom = np.concatenate([t[2], t[3]], -1)
    return np.concatenate([top, bottom], -2)


def random_crop_flip(x, y, size, rng):
    h, w = y.shape
    i, j = rng.integers(0, h - size + 1), rng.integers(0, w - size + 1)
    cx, cy = x[:, i:i + size, j:j + size], y[i:i + size, j:j + size]
    if rng.random() > 0.5:
        cx, cy = cx[:, :, ::-1], cy[:, ::-1]
    if rng.random() > 0.5:
        cx, cy = cx[:, ::-1, :], cy[::-1, :]
    return np.ascontiguousarray(cx), np.ascontiguousarray(cy)

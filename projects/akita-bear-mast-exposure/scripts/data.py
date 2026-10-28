"""Inputs aligned on the prefecture cells of akita-bear-risk-grid-100m (row-major over [iy, ix], row 0 = south,
the order of its saved scores): the saved B_env surfaces, the yearly report labels and counts, the exposure,
the 10 km blocks, and the Akita mast scarcity (5 - index).
"""

import csv
import hashlib

import numpy as np

SURFACE = {2024: "b1_dev_2023_to_2024", 2025: "b2_confirm_2023-2024_to_2025", 2026: "b3_confirm_2023-2025_to_2026"}
TRAIN = {2024: [2023], 2025: [2023, 2024], 2026: [2023, 2024, 2025]}
MAX_INDEX = 5.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mast_scarcity(rows, stage):
    """{year: 5 - index} for Akita from (year, pref, stage, index) rows."""
    return {int(y): round(MAX_INDEX - float(i), 6) for y, p, s, i in rows if p == "秋田県" and s == stage}


def read_mast(path, stage):
    with open(path, encoding="utf-8") as f:
        rows = [(r["year"], r["pref"], r["stage"], r["index"]) for r in csv.DictReader(f)]
    return mast_scarcity(rows, stage)


def vec(a, muni):
    return a[muni >= 0]


def exposure_vec(e, name, muni):
    """The exposure on the prefecture cells, NaN (no mapped vegetation within the radius, water) set to 0."""
    v = vec(np.asarray(e[name], dtype=float), muni)
    n = int(np.isnan(v).sum())
    return np.nan_to_num(v, nan=0.0), n


def load(bear, art):
    import pandas as pd

    muni = np.load(f"{bear}/grid_mask.npz")["muni"]
    rep = np.load(f"{bear}/reports_by_year.npz")
    counts = {int(k[1:]): vec(rep[k], muni).astype(float) for k in rep.files}
    cells = pd.read_parquet(f"{bear}/cells.parquet", columns=["ix", "iy", "code5"])
    blocks = (cells.ix.to_numpy() // 100) * 10000 + cells.iy.to_numpy() // 100  # 10 km x 10 km, as the bear project
    benv = {t: np.load(f"{bear}/eval/{f}_scores.npz")["B_env"].astype(float) for t, f in SURFACE.items()}
    e = np.load(f"{art}/exposure.npz")
    return {"muni": muni, "counts": counts, "blocks": blocks, "cells": cells, "benv": benv, "exposure": e}

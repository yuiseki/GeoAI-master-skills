"""uvx --python 3.12 --with numpy --with scipy --with pyproj --with pytest pytest -q -p no:cacheprovider test_blocks.py"""

# groups and decide of 03_blocks.py, and common.box_utm.
import importlib

import numpy as np
from pyproj import Transformer

import common

bk = importlib.import_module("03_blocks")


def test_box_utm_is_snapped_outward_and_covers_every_edge_point():
    x0, y0, x1, y1 = common.box_utm()
    assert all(v % 10 == 0 for v in (x0, y0, x1, y1)) and x0 < x1 and y0 < y1
    w, s, e, n = common.BOX_LONLAT
    t = Transformer.from_crs("EPSG:4326", common.UTM, always_xy=True)
    lon = np.r_[np.linspace(w, e, 50), np.linspace(w, e, 50), np.full(50, w), np.full(50, e)]
    lat = np.r_[np.full(50, s), np.full(50, n), np.linspace(s, n, 50), np.linspace(s, n, 50)]
    xs, ys = t.transform(lon, lat)
    assert xs.min() >= x0 and xs.max() <= x1 and ys.min() >= y0 and ys.max() <= y1
    assert xs.min() - x0 < 10 and y1 - ys.max() < 10


def aux_line():
    # 8 pixels in a row: 0-1 recorded flood (REC), 2 near the river and outside A31a (channel), 3-4 in A31a,
    # 5 too close to REC for a control, 6-7 controls; pixel 7 is not valid.
    return {"a31a": np.array([0, 0, 0, 1, 1, 0, 0, 0], bool),
            "rec": np.array([1, 1, 0, 0, 0, 0, 0, 0], bool),
            "dist_tama": np.array([900, 900, 100, 100, 900, 900, 900, 900], float),
            "dist_rec": np.array([0, 0, 100, 200, 300, 200, 400, 500], float)}


def test_groups_are_disjoint_and_follow_the_rules():
    aux = aux_line()
    valid = np.array([1, 1, 1, 1, 1, 1, 1, 0], bool)
    g = bk.groups(aux, valid)
    assert np.flatnonzero(g["REC"]).tolist() == [0, 1]
    assert np.flatnonzero(g["CHANNEL"]).tolist() == [2]
    # pixel 3 is in A31a and within 300 m of the river: A31a keeps it (the channel is outside A31a only)
    assert np.flatnonzero(g["A31A"]).tolist() == [3, 4]
    assert np.flatnonzero(g["CTRL"]).tolist() == [6]
    stacked = np.stack(list(g.values())).sum(axis=0)
    assert stacked.max() == 1
    # ctrl_any lets A31a pixels far from REC be controls too (pixel 4 at 300 m)
    assert np.flatnonzero(bk.groups(aux, valid, ctrl_any=True)["CTRL"]).tolist() == [4, 6]
    # a narrower channel drops pixel 2 from CHANNEL, but the CTRL rule still excludes the 300 m strip
    g2 = bk.groups(aux, valid, ch_w=50.0)
    assert not g2["CHANNEL"].any() and not g2["CTRL"][2]


def m(b0=(0.375, 0.125), b1=(0.5, 0.25), b2=(0.25, 0.125), lift=2.0):  # exact in binary
    return {"B0": {"p_target": b0[0], "p_ref_std": b0[1]}, "B1": {"p_target": b1[0], "p_ref_std": b1[1]},
            "B2": {"p_target": b2[0], "p_ref_std": b2[1]}, "B3": {"lift": lift}}


def test_decide_at_the_boundaries():
    assert set(bk.decide(m()).values()) == {"supported"}
    d = bk.decide(m(b0=(0.29, 0.01), b1=(0.49, 0.25), b2=(0.2, 0.11), lift=1.99))
    assert d == {"C0": "rejected", "C1": "rejected", "C2": "rejected", "C3": "rejected", "C4": "rejected"}
    assert bk.decide(m(b0=(0.6, 0.21)))["C0"] == "rejected"          # 0.6 < 3 x 0.21
    assert bk.decide(m(b1=(0.6, 0.31)))["C1"] == "rejected" and bk.decide(m(b1=(0.6, 0.31)))["C2"] == "supported"

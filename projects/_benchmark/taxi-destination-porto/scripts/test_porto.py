"""uvx --python 3.12 --with numpy --with pytest pytest -q scripts/test_porto.py"""

import math

import numpy as np
import pytest

from porto import (equirectangular, first_last_k, haversine, parse_polyline, sample_prefixes, snapshot_cut,
                   uniform_cuts)


def test_haversine_matches_a_hand_value():
    # one degree of latitude on a 6371 km sphere
    assert haversine(41.0, -8.6, 42.0, -8.6) == pytest.approx(6371 * math.pi / 180, rel=1e-9)
    # vectorised and symmetric
    a = haversine(np.array([41.15, 41.16]), np.array([-8.61, -8.62]), np.array([41.16, 41.15]), np.array([-8.62, -8.61]))
    assert a[0] == pytest.approx(a[1])


def test_equirectangular_is_close_to_haversine_at_city_scale():
    h = haversine(41.15, -8.61, 41.18, -8.58)
    e = equirectangular(41.15, -8.61, 41.18, -8.58)
    assert e == pytest.approx(h, rel=1e-3)


def test_parse_polyline_keeps_lon_lat_order():
    p = parse_polyline("[[-8.618643,41.141412],[-8.618499,41.141376]]")
    assert p.shape == (2, 2) and p[0, 0] == pytest.approx(-8.618643) and p[0, 1] == pytest.approx(41.141412)
    assert parse_polyline("[]").shape == (0, 2)


def test_snapshot_cut_keeps_the_points_up_to_the_cut():
    # start 1000, 5 points -> points at 1000, 1015, 1030, 1045, 1060
    starts, lens = np.array([1000, 2000, 1050]), np.array([5, 3, 1])
    trip, n = snapshot_cut(starts, lens, [1030])
    assert trip.tolist() == [0] and n.tolist() == [3]          # 1000,1015,1030 known
    trip, n = snapshot_cut(starts, lens, [1060])
    assert trip.tolist() == [0] and n.tolist() == [5]          # the last point exactly at the cut
    trip, n = snapshot_cut(starts, lens, [1050])
    assert sorted(trip.tolist()) == [0, 2] and dict(zip(trip.tolist(), n.tolist())) == {0: 4, 2: 1}
    _, _, at = snapshot_cut(starts, lens, [1050, 1030], return_cut=True)
    assert at.tolist() == [1030, 1050]


def test_snapshot_cut_takes_a_trip_once():
    starts, lens = np.array([1000]), np.array([100])
    trip, n = snapshot_cut(starts, lens, [1100, 1200])
    assert trip.tolist() == [0] and n.tolist() == [7]          # the first cut that catches it


def test_uniform_cuts_are_reproducible_and_in_range():
    a, b = uniform_cuts(100, 200, 50, seed=42), uniform_cuts(100, 200, 50, seed=42)
    assert (a == b).all() and a.min() >= 100 and a.max() < 200 and len(a) == 50


def test_first_last_k_pads_by_repeating_the_ends():
    p = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    x = first_last_k(p, 2)
    assert x.tolist() == [[0, 0], [1, 1], [1, 1], [2, 2]]
    x = first_last_k(p[:1], 3)
    assert x.tolist() == [[0, 0]] * 6
    long = np.arange(20, dtype=float).reshape(10, 2)
    assert first_last_k(long, 2).tolist() == [[0, 1], [2, 3], [16, 17], [18, 19]]


def test_sample_prefixes_is_uniform_over_all_prefixes():
    lens = np.array([1, 3])                                    # 4 prefixes: (0,1) (1,1) (1,2) (1,3)
    rng = np.random.default_rng(0)
    trip, n = sample_prefixes(lens, 200000, rng)
    assert (n >= 1).all() and (n <= lens[trip]).all()
    assert (trip == 0).mean() == pytest.approx(0.25, abs=0.01)
    for k in (1, 2, 3):
        assert ((trip == 1) & (n == k)).mean() == pytest.approx(0.25, abs=0.01)


def test_batch_first_last_matches_the_single_version():
    from porto import batch_first_last
    rng = np.random.default_rng(3)
    lens = np.array([1, 4, 12, 7])
    off = np.concatenate([[0], np.cumsum(lens)])
    lat = rng.random(off[-1]); lon = rng.random(off[-1])
    trip = np.array([0, 1, 2, 2, 3]); n = np.array([1, 3, 12, 2, 7])
    got = batch_first_last(lat, lon, off, trip, n, 5)        # (batch, 2k, 2) as (lat, lon)
    for b in range(len(trip)):
        s = off[trip[b]]
        pts = np.stack([lat[s:s + n[b]], lon[s:s + n[b]]], 1)
        assert np.allclose(got[b], first_last_k(pts, 5))


def test_time_features_use_porto_local_time():
    from porto import time_features
    # 2013-07-01 00:07:00 UTC is 01:07 in Lisbon (summer time), a Monday
    q, dow, week = time_features(np.array([1372637220]))
    assert q.tolist() == [4] and dow.tolist() == [0] and 0 <= week[0] < 52


def test_cluster_output_stays_in_the_hull():
    torch = pytest.importorskip("torch")
    from model import DestMLP
    centres = np.array([[41.1, -8.6], [41.2, -8.5], [41.15, -8.7]])
    m = DestMLP(centres, n_points=10, emb_sizes={"taxi": 5}, emb_dim=4, hidden=8)
    x = torch.randn(6, 20)
    meta = {"taxi": torch.tensor([0, 1, 2, 3, 4, 0])}
    y = m(x, meta).detach().numpy()
    assert y.shape == (6, 2)
    assert (y[:, 0] >= 41.1 - 1e-6).all() and (y[:, 0] <= 41.2 + 1e-6).all()
    m0 = DestMLP(centres, n_points=10, emb_sizes={}, emb_dim=4, hidden=8)
    assert m0(x, {}).shape == (6, 2)


def test_equirectangular_loss_is_zero_at_the_target_and_matches_numpy():
    torch = pytest.importorskip("torch")
    from model import equirect_loss
    p = torch.tensor([[41.15, -8.61], [41.18, -8.58]], dtype=torch.float64)
    t = torch.tensor([[41.15, -8.61], [41.15, -8.61]], dtype=torch.float64)
    v = equirect_loss(p, t, reduce=False).numpy()
    assert v[0] == pytest.approx(0, abs=1e-3) and v[1] == pytest.approx(equirectangular(41.18, -8.58, 41.15, -8.61), rel=1e-9)

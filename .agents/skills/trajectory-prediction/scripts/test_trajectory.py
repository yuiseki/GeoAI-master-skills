"""uvx --python 3.12 --with numpy --with pandas --with pytest pytest -q test_trajectory.py"""

import math

import numpy as np
import pytest

from trajectory import (batch_first_last, boot_by_group, equirectangular, first_last_k, haversine, last_point,
                        paired_difference, parse_polyline, sample_prefixes, snapshot_cut, time_features, uniform_cuts)


def test_haversine_matches_a_hand_value():
    assert haversine(41.0, -8.6, 42.0, -8.6) == pytest.approx(6371 * math.pi / 180, rel=1e-9)
    a = haversine(np.array([41.15, 41.16]), np.array([-8.61, -8.62]), np.array([41.16, 41.15]), np.array([-8.62, -8.61]))
    assert a[0] == pytest.approx(a[1])


def test_equirectangular_is_close_to_haversine_at_city_scale():
    assert equirectangular(41.15, -8.61, 41.18, -8.58) == pytest.approx(haversine(41.15, -8.61, 41.18, -8.58), rel=1e-3)


def test_parse_polyline_keeps_lon_lat_order():
    p = parse_polyline("[[-8.618643,41.141412],[-8.618499,41.141376]]")
    assert p.shape == (2, 2) and p[0, 0] == pytest.approx(-8.618643) and p[0, 1] == pytest.approx(41.141412)
    assert parse_polyline("[]").shape == (0, 2)


def test_snapshot_cut_keeps_the_points_up_to_the_cut():
    starts, lens = np.array([1000, 2000, 1050]), np.array([5, 3, 1])     # points every 15 s
    trip, n = snapshot_cut(starts, lens, [1030])
    assert trip.tolist() == [0] and n.tolist() == [3]
    trip, n = snapshot_cut(starts, lens, [1060])
    assert trip.tolist() == [0] and n.tolist() == [5]                     # cut exactly at the last point
    trip, n, at = snapshot_cut(starts, lens, [1050, 1030], return_cut=True)
    assert trip.tolist() == [0, 2] and at.tolist() == [1030, 1050] and n.tolist() == [3, 1]   # track 0 once, at its first cut
    trip, n = snapshot_cut(starts, lens, [1050])
    assert dict(zip(trip.tolist(), n.tolist())) == {0: 4, 2: 1}


def test_snapshot_cut_with_another_sampling_step():
    trip, n = snapshot_cut(np.array([0]), np.array([10]), [25], step=10)
    assert n.tolist() == [3]


def test_uniform_cuts_are_reproducible_and_in_range():
    a, b = uniform_cuts(100, 200, 50, seed=42), uniform_cuts(100, 200, 50, seed=42)
    assert (a == b).all() and a.min() >= 100 and a.max() < 200 and len(a) == 50


def test_first_last_k_pads_by_repeating_the_ends():
    p = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    assert first_last_k(p, 2).tolist() == [[0, 0], [1, 1], [1, 1], [2, 2]]
    assert first_last_k(p[:1], 3).tolist() == [[0, 0]] * 6


def test_batch_first_last_matches_the_single_version():
    rng = np.random.default_rng(3)
    lens = np.array([1, 4, 12, 7])
    off = np.concatenate([[0], np.cumsum(lens)])
    lat, lon = rng.random(off[-1]), rng.random(off[-1])
    trip, n = np.array([0, 1, 2, 2, 3]), np.array([1, 3, 12, 2, 7])
    got = batch_first_last(lat, lon, off, trip, n, 5)
    for b in range(len(trip)):
        s = off[trip[b]]
        assert np.allclose(got[b], first_last_k(np.stack([lat[s:s + n[b]], lon[s:s + n[b]]], 1), 5))


def test_last_point_is_the_prefix_end():
    lat, lon = np.arange(10.0), -np.arange(10.0)
    off = np.array([0, 4, 10])
    p = last_point(lat, lon, off, np.array([0, 1]), np.array([2, 6]))
    assert p.tolist() == [[1, -1], [9, -9]]


def test_sample_prefixes_is_uniform_over_all_prefixes():
    lens = np.array([1, 3])
    trip, n = sample_prefixes(lens, 200000, np.random.default_rng(0))
    assert (n >= 1).all() and (n <= lens[trip]).all()
    assert (trip == 0).mean() == pytest.approx(0.25, abs=0.01)
    for k in (1, 2, 3):
        assert ((trip == 1) & (n == k)).mean() == pytest.approx(0.25, abs=0.01)
    a = sample_prefixes(lens, 100, np.random.default_rng(5))
    b = sample_prefixes(lens, 100, np.random.default_rng(5), cum=np.cumsum(lens))
    assert (a[0] == b[0]).all() and (a[1] == b[1]).all()


def test_time_features_use_the_local_time_zone():
    q, dow, week = time_features(np.array([1372637220]), "Europe/Lisbon")   # 01:07 local, a Monday
    assert q.tolist() == [4] and dow.tolist() == [0] and 0 <= week[0] < 52
    q, _, _ = time_features(np.array([1372637220]), "UTC")
    assert q.tolist() == [0]


def test_boot_by_group_is_wider_than_by_row_when_groups_share_errors():
    rng = np.random.default_rng(1)
    g = np.repeat(np.arange(50), 40)
    e = rng.normal(0, 1, 50)[g] + rng.normal(0, 0.1, len(g))         # errors shared within a cut time
    lo_g, hi_g = boot_by_group(e, g)
    lo_r, hi_r = boot_by_group(e, np.arange(len(e)))
    assert (hi_g - lo_g) > 3 * (hi_r - lo_r)
    assert lo_g < e.mean() < hi_g


def test_paired_difference_resamples_both_models_together():
    rng = np.random.default_rng(2)
    g = np.repeat(np.arange(100), 20)
    shared = rng.normal(3, 1, 100)[g]                                  # both models suffer on the same cut times
    a, b = shared + 0.2, shared + rng.normal(0, 0.05, len(g))
    d, lo, hi = paired_difference(a, b, g)
    assert d == pytest.approx(0.2, abs=0.02) and lo > 0.15 and hi < 0.25

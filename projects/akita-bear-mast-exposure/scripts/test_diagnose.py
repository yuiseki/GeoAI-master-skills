"""Tests for the exploratory exposure classes and region groups."""

import numpy as np

import diagnose as dg


def test_classes_zero_then_quartiles_of_positive_values():
    e = np.array([0, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    edges = dg.class_edges(e)
    k = dg.classes(e, edges)
    assert list(k[:2]) == [0, 0] and set(k[2:]) == {1, 2, 3, 4}
    assert (np.bincount(k)[1:] == 2).all()


def test_top_mask_takes_ceil_five_percent():
    s = np.arange(100.0)
    m = dg.top_mask(s, 0.05)
    assert m.sum() == 5 and m[-5:].all()


def test_regions_cover_all_25_municipalities_once():
    names = [n for r in dg.REGIONS.values() for n in r]
    assert len(names) == len(set(names)) == 25

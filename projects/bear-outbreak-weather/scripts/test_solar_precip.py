import numpy as np
from affine import Affine
from shapely.geometry import box

import solar_precip as sp


def centres_marked(m, t):
    r0, c0, nr, nc, mask = m
    rr, cc = np.nonzero(mask)
    return sorted(zip(np.round(t.c + (c0 + cc + 0.5) * t.a, 2), np.round(t.f + (r0 + rr + 0.5) * t.e, 2)))


def test_window_mask_marks_exactly_the_pixel_centres_inside():
    t = Affine(0.1, 0, -180.0, 0, -0.1, 90.0)  # the AgERA5 grid
    m = sp.window_masks({"a": box(140.0, 39.0, 140.3, 39.2)}, t)["a"]
    got = centres_marked(m, t)
    want = sorted((round(x, 2), round(y, 2)) for x in (140.05, 140.15, 140.25) for y in (39.05, 39.15))
    assert got == want
    m = sp.window_masks({"b": box(140.0, 39.0, 140.14, 39.1)}, t)["b"]
    assert centres_marked(m, t) == [(140.05, 39.05)]

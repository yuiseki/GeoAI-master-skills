"""uvx --python 3.12 --with numpy --with pytest pytest -q test_s1f11.py"""

import numpy as np
import pytest

from s1f11 import IGNORE, chip_iou, flood_permanent, labels_to_target, pooled_iou, preprocess, random_crop_flip, tiles4, untile4


def test_preprocess_clips_scales_and_standardises_like_the_notebook():
    x = np.array([[[-60.0, -50.0, 1.0, np.nan]], [[0.0, 2.0, -25.0, -50.0]]], dtype="float32")   # (2 bands, 1, 4)
    got = preprocess(x)
    vv = (np.array([0.0, 0.0, 1.0, (0 + 50) / 51]) - 0.6851) / 0.0820          # nan -> 0 dB, then clip and scale
    vh = (np.array([50 / 51, 1.0, 25 / 51, 0.0]) - 0.5235) / 0.1102
    assert np.allclose(got[0, 0], vv, atol=1e-5) and np.allclose(got[1, 0], vh, atol=1e-5)


def test_labels_to_target_marks_invalid_as_ignore():
    t = labels_to_target(np.array([[-1, 0, 1]], dtype="int16"))
    assert t.tolist() == [[IGNORE, 0, 1]]


def test_chip_iou_ignores_invalid_and_follows_the_epsilon_rule():
    t = np.array([[1, 1, 0, IGNORE]])
    assert chip_iou(np.array([[1, 0, 0, 1]]), t) == pytest.approx(0.5)
    assert chip_iou(np.array([[0, 0, 0, 0]]), np.array([[0, 0, 0, IGNORE]])) == pytest.approx(1.0)   # 0/0 -> 1
    assert chip_iou(np.array([[1, 0, 0, 0]]), np.array([[0, 0, 0, 0]])) == pytest.approx(0.0, abs=1e-6)


def test_pooled_iou_sums_pixels_over_chips():
    p = [np.array([[1, 1]]), np.array([[0, 0]])]
    t = [np.array([[1, 0]]), np.array([[1, IGNORE]])]
    assert pooled_iou(p, t) == pytest.approx(1 / 3)          # I = 1, U = 3


def test_flood_permanent_split_uses_the_jrc_layer():
    t = np.array([[1, 1, 0, IGNORE]])
    jrc = np.array([[1, 0, 1, 0]])
    p = np.array([[1, 1, 1, 0]])
    (pf, tf), (pp, tp) = flood_permanent(p, t, jrc)
    # flood: permanent pixels are left out; permanent: only the water target on permanent pixels counts as water
    assert tf.tolist() == [[IGNORE, 1, IGNORE, IGNORE]] and pf.tolist() == [[1, 1, 1, 0]]
    assert tp.tolist() == [[1, 0, 0, IGNORE]]


def test_tiles4_and_back():
    a = np.arange(2 * 512 * 512).reshape(2, 512, 512)
    t = tiles4(a)
    assert t.shape == (4, 2, 256, 256) and (t[1] == a[:, :256, 256:]).all() and (t[2] == a[:, 256:, :256]).all()
    assert (untile4(t) == a).all()


def test_random_crop_flip_keeps_image_and_label_together():
    rng = np.random.default_rng(0)
    x = np.arange(512 * 512, dtype="float32").reshape(1, 512, 512).repeat(2, 0)
    y = np.arange(512 * 512).reshape(512, 512)
    for _ in range(20):
        cx, cy = random_crop_flip(x, y, 256, rng)
        assert cx.shape == (2, 256, 256) and cy.shape == (256, 256) and (cx[0] == cy).all() and (cx[1] == cy).all()

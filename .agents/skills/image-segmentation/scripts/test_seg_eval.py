"""uvx --python 3.12 --with numpy --with scipy --with pytest pytest -q test_seg_eval.py"""

import numpy as np
import pytest

from seg_eval import (IGNORE, boot_by_group, chip_iou, otsu_mask, otsu_threshold, paired_difference, pooled_iou,
                      random_crop_flip, tiles, untile)


def test_otsu_splits_two_separated_modes():
    rng = np.random.default_rng(0)
    v = np.concatenate([rng.normal(-25, 1, 3000), rng.normal(-10, 1, 7000)])
    t = otsu_threshold(v)
    assert -22 < t < -13


def test_otsu_mask_marks_the_dark_side_as_water_and_skips_nan():
    rng = np.random.default_rng(1)
    img = np.where(rng.random((64, 64)) < 0.3, rng.normal(-25, 1, (64, 64)), rng.normal(-12, 1, (64, 64)))
    img[0, 0] = np.nan
    m = otsu_mask(img)
    assert m[0, 0] == 0 and abs(m.mean() - 0.3) < 0.03
    assert (img[m == 1] < -18).all()


def test_otsu_mask_of_a_flat_image_is_empty():
    assert otsu_mask(np.full((8, 8), -12.0)).sum() == 0


def test_chip_iou_ignores_invalid_and_follows_the_epsilon_rule():
    t = np.array([[1, 1, 0, IGNORE]])
    assert chip_iou(np.array([[1, 0, 0, 1]]), t) == pytest.approx(0.5)
    assert chip_iou(np.array([[0, 0, 0, 0]]), np.array([[0, 0, 0, IGNORE]])) == pytest.approx(1.0)
    assert chip_iou(np.array([[1, 0, 0, 0]]), np.array([[0, 0, 0, 0]])) == pytest.approx(0.0, abs=1e-6)


def test_pooled_iou_sums_pixels_over_chips():
    assert pooled_iou([np.array([[1, 1]]), np.array([[0, 0]])],
                      [np.array([[1, 0]]), np.array([[1, IGNORE]])]) == pytest.approx(1 / 3)


def test_chip_mean_and_pooled_can_rank_two_predictions_differently():
    t = [np.array([[1] * 100]), np.array([[0, 0, 0, 1]])]
    a = [np.array([[1] * 100]), np.array([[1, 1, 1, 1]])]       # perfect on the big chip, poor on the small one
    b = [np.array([[1] * 60 + [0] * 40]), np.array([[0, 0, 0, 1]])]
    assert pooled_iou(a, t) > pooled_iou(b, t)
    assert np.mean([chip_iou(p, y) for p, y in zip(a, t)]) < np.mean([chip_iou(p, y) for p, y in zip(b, t)])


def test_tiles_and_back():
    a = np.arange(2 * 512 * 512).reshape(2, 512, 512)
    t = tiles(a, 256)
    assert t.shape == (4, 2, 256, 256) and (t[1] == a[:, :256, 256:]).all() and (t[2] == a[:, 256:, :256]).all()
    assert (untile(t, 512) == a).all()


def test_random_crop_flip_keeps_image_and_label_together():
    rng = np.random.default_rng(0)
    x = np.arange(64 * 64, dtype="float32").reshape(1, 64, 64).repeat(2, 0)
    y = np.arange(64 * 64).reshape(64, 64)
    for _ in range(20):
        cx, cy = random_crop_flip(x, y, 32, rng)
        assert cx.shape == (2, 32, 32) and (cx[0] == cy).all() and (cx[1] == cy).all()


def test_group_intervals_are_wider_when_chips_of_one_event_agree():
    rng = np.random.default_rng(1)
    g = np.repeat(np.arange(10), 9)
    x = rng.normal(0, 0.1, 10)[g] + rng.normal(0, 0.01, len(g))
    lo_g, hi_g = boot_by_group(x, g)
    lo_c, hi_c = boot_by_group(x, np.arange(len(x)))
    assert hi_g - lo_g > 2 * (hi_c - lo_c)
    d, lo, hi = paired_difference(x + 0.05, x, g)
    assert d == pytest.approx(0.05) and lo == pytest.approx(0.05) and hi == pytest.approx(0.05)


def test_scene_threshold_uses_the_high_variance_cells():
    from seg_eval import scene_otsu_threshold
    rng = np.random.default_rng(2)
    img = rng.normal(-12, 1, (400, 400))                    # mostly land
    img[:100, :150] = rng.normal(-25, 1, (100, 150))         # one lake across a cell edge
    t_all = otsu_threshold(img.ravel())
    t = scene_otsu_threshold(img, cell=100, top=0.25)
    assert -22 < t < -14
    # the whole-scene histogram is dominated by land; the high-variance cells hold both classes
    assert abs(t - (-18.5)) <= abs(t_all - (-18.5)) + 1.0


def test_focal_mean_ignores_nan():
    from seg_eval import focal_mean
    a = np.array([[1.0, np.nan, 3.0]])
    assert np.allclose(focal_mean(a, 3), [[1.0, 2.0, 3.0]])

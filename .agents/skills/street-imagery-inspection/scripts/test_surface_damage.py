"""uvx --with numpy --with pillow --with scikit-learn --with pytest pytest test_surface_damage.py"""

# Tests for surface_damage.py without the image model: the patches cut from labelled road images, the grouped
# evaluation (no image in both train and test), and the probe saved and read back.

import io
import zipfile

import numpy as np
import pytest
from PIL import Image

from surface_damage import fit_probe, grid_patches, negative_boxes, parse_voc, predict, rdd_patches

XML = """<annotation><filename>{f}</filename><size><width>600</width><height>600</height></size>
{objs}</annotation>"""
OBJ = "<object><name>{n}</name><bndbox><xmin>{a}</xmin><ymin>{b}</ymin><xmax>{c}</xmax><ymax>{d}</ymax></bndbox></object>"


def rdd_zip(path, n=6):
    with zipfile.ZipFile(path, "w") as z:
        for i in range(n):
            f = f"X_{i:06d}.jpg"
            buf = io.BytesIO()
            Image.new("RGB", (600, 600), (100, 100, 100)).save(buf, "JPEG")
            z.writestr(f"X/train/images/{f}", buf.getvalue())
            objs = OBJ.format(n="D40", a=250, b=400, c=330, d=460) if i % 2 == 0 else ""
            z.writestr(f"X/train/annotations/xmls/{f[:-4]}.xml", XML.format(f=f, objs=objs))
    return path


def test_parse_voc():
    t = XML.format(f="a.jpg", objs=OBJ.format(n="D00", a=1, b=2, c=30, d=40) + OBJ.format(n="D20", a=5, b=6, c=7, d=8))
    f, boxes = parse_voc(t)
    assert f == "a.jpg" and boxes == [("D00", (1, 2, 30, 40)), ("D20", (5, 6, 7, 8))]


def test_negatives_stay_on_the_road_and_off_the_damage():
    rng = np.random.default_rng(0)
    boxes = [(200, 380, 420, 520)]
    neg = negative_boxes(600, 600, boxes, 5, rng)
    assert len(neg) == 5
    for x0, y0, x1, y1 in neg:
        assert y0 >= 0.5 * 600 and y1 <= 0.92 * 600
        assert x1 <= boxes[0][0] or x0 >= boxes[0][2] or y1 <= boxes[0][1] or y0 >= boxes[0][3]


def test_rdd_patches_label_and_group(tmp_path):
    z = rdd_zip(tmp_path / "x.zip")
    rows = list(rdd_patches(z, neg_per_image=2, seed=0))
    pos = [r for r in rows if r["damage"]]
    assert len(pos) == 3 and {r["classes"] for r in pos} == {"D40"}
    assert len([r for r in rows if not r["damage"]]) == 12
    assert all(r["patch"].size == (224, 224) for r in rows)
    assert {r["image"] for r in pos} == {"X_000000.jpg", "X_000002.jpg", "X_000004.jpg"}


def test_grouped_evaluation_and_saved_probe(tmp_path):
    rng = np.random.default_rng(1)
    n = 400
    y = rng.integers(0, 2, n)
    emb = rng.normal(size=(n, 16)) + y[:, None] * 1.5
    groups = np.repeat(np.arange(100), 4)
    res = fit_probe(emb, y, groups, tmp_path / "probe.npz")
    assert res["auc"] > 0.9 and res["folds"] == 5
    assert res["test_images_overlap_train"] == 0
    p = predict(emb[:3], tmp_path / "probe.npz")
    assert p.shape == (3,) and np.all((p >= 0) & (p <= 1))


def test_grid_patches_cover_the_road_part_of_a_view():
    img = Image.new("RGB", (800, 600))
    boxes = grid_patches(img.size, top=0.5, bottom=0.95, patch=150)
    assert boxes and all(b[1] >= 300 and b[3] <= 570 for b in boxes)
    assert all(b[2] - b[0] == 150 for b in boxes)


def test_a_saved_probe_is_scored_on_other_labelled_patches(tmp_path):
    from surface_damage import score
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 300)
    emb = rng.normal(size=(300, 8)) + y[:, None] * 2.0
    fit_probe(emb, y, np.arange(300) // 3, tmp_path / "probe.npz")
    s = score(emb, y, tmp_path / "probe.npz")
    assert s["auc"] > 0.9 and s["patches"] == 300 and s["positives"] == int(y.sum())
    assert 0 <= s["precision_at_0.5"] <= 1 and 0 <= s["recall_at_0.5"] <= 1

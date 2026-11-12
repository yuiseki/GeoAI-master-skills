"""uvx --with pytest pytest test_panoramax_fetch.py"""

# Tests for panoramax_fetch.py without the network: the tiling splits a tile that hit the page limit, the
# filters count every picture, and the sample is uniform, fixed by the seed and drawn after the filters.

import pytest

from panoramax_fetch import feature_row, list_pictures, sample


def feat(i, lon, lat, producer="bordeaux métropole", fov=360, date="2025-10-02T10:00:00+00:00"):
    return {"id": f"p{i}", "collection": "c", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"datetime": date, "view:azimuth": 90, "license": "etalab-2.0",
                           "geovisio:producer": producer, "original_file:size": 100,
                           "pers:interior_orientation": {"field_of_view": fov, "camera_model": "Ladybug"},
                           "annotations": [{"id": "a"}]},
            "assets": {"sd": {"href": f"https://x/{i}/sd.jpg"}, "hd": {"href": f"https://x/{i}/hd.jpg"}}}


def fake_search(points, limit):
    calls = []

    def search(bbox, lim):
        calls.append(bbox)
        w, s, e, n = bbox
        hits = [feat(i, x, y) for i, (x, y) in enumerate(points) if w <= x < e and s <= y < n]
        return hits[:lim]
    return search, calls


def test_a_full_tile_is_split_until_every_picture_is_listed():
    pts = [(0.001 * i, 0.0005) for i in range(10)]
    search, calls = fake_search(pts, 4)
    got = list_pictures((0.0, 0.0, 0.01, 0.001), search, limit=4, tile=0.01)
    assert sorted(f["id"] for f in got) == sorted(f"p{i}" for i in range(10))
    assert len(calls) > 1


def test_rows_and_filters_are_counted():
    feats = [feat(1, 0, 0), feat(2, 0, 0, producer="someone"), feat(3, 0, 0, fov=96),
             feat(4, 0, 0, date="2020-01-01T00:00:00+00:00")]
    rows = [feature_row(f) for f in feats]
    kept, audit = sample(rows, n=10, seed=0, producer="bordeaux métropole", fov=360, since="2025-01-01")
    assert [r["id"] for r in kept] == ["p1"]
    assert audit == {"listed": 4, "other_producer": 1, "other_fov": 1, "too_old": 1, "eligible": 1, "sampled": 1}
    assert rows[0]["annotations"] == 1 and rows[0]["hd"].endswith("hd.jpg") and rows[0]["lon"] == 0


def test_the_sample_is_fixed_by_the_seed_and_without_replacement():
    rows = [feature_row(feat(i, 0, 0)) for i in range(100)]
    a, _ = sample(rows, n=20, seed=7)
    b, _ = sample(rows, n=20, seed=7)
    assert [r["id"] for r in a] == [r["id"] for r in b] and len({r["id"] for r in a}) == 20

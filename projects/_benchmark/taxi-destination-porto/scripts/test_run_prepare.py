"""uvx --python 3.12 --with numpy --with pandas --with pytest pytest -q -p no:cacheprovider test_run_prepare.py"""

# Pure helpers of run.py (dest, split, meta_maps, meta_of, emb_sizes, boot_by_cut) and prepare.py (sha, flat_points,
# table). No torch: run.py imports it only inside the training functions.
import hashlib

import numpy as np
import pandas as pd
import pytest

import prepare
import run


def trips():
    # 4 trips with 2, 1, 3 and 0 points
    lens = np.array([2, 1, 3, 0])
    off = np.concatenate([[0], np.cumsum(lens)])
    return dict(lat=np.array([41.1, 41.2, 41.3, 41.4, 41.5, 41.6], "float32"),
                lon=np.array([-8.6, -8.5, -8.4, -8.3, -8.2, -8.1], "float32"), off=off, lens=lens,
                origin_call=np.array([0, 20, 10, 30]), origin_stand=np.array([0, 5, 70, 63]),
                taxi_id=np.array([7, 9, 7, 8]), day_type=np.array([0, 0, 0, 0], np.int8),
                timestamp=np.array([1372636800, 1372640400, 1372644000, 1372647600]))


def test_dest_is_the_last_point():
    d = run.dest(trips(), np.array([0, 2]))
    assert np.allclose(d, [[41.2, -8.5], [41.6, -8.1]], atol=1e-5)


def test_meta_maps_and_meta_of_map_unseen_ids_to_zero():
    t = trips()
    maps = run.meta_maps(t, np.array([0, 1, 2]))
    assert maps["calls"].tolist() == [10, 20] and maps["taxis"].tolist() == [7, 9]
    m = run.meta_of(t, np.arange(4), maps)
    assert m["origin_call"].tolist() == [0, 2, 1, 0]           # 0 = no caller; 30 was not seen in training
    assert m["taxi"].tolist() == [1, 2, 1, 0]                  # taxi 8 not seen
    assert m["origin_stand"].tolist() == [0, 5, 63, 63]        # clipped into the 64 embeddings
    sizes = run.emb_sizes(maps)
    assert sizes["origin_call"] == 3 and sizes["taxi"] == 3 and sizes["qhour"] == 96
    assert all(m[k].max() < sizes[k] for k in sizes)


def test_boot_by_cut_resamples_whole_cut_times():
    err = np.array([1.0, 1.0, 3.0, 3.0])
    lo, hi = run.boot_by_cut(err, np.array([0, 0, 0, 0]))
    assert (lo, hi) == (2.0, 2.0)                    # one group: every draw is the overall mean
    lo, hi = run.boot_by_cut(err, np.array([5, 5, 6, 6]), reps=4000)
    assert (lo, hi) == (1.0, 3.0)                              # a quarter of the draws pick one group twice


def test_split_rejects_an_unknown_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "ART", tmp_path)
    with pytest.raises(ValueError):
        run.split(trips(), "other")


def test_split_reuses_a_saved_split(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "ART", tmp_path)
    np.savez(tmp_path / "split_rand.npz", train=np.array([0, 2]), test_trip=np.array([1]))
    s = run.split(trips(), "rand")
    assert s["train"].tolist() == [0, 2] and s["test_trip"].tolist() == [1]


def test_sha_of_a_file(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"abc" * 1000)
    assert prepare.sha(p) == hashlib.sha256(b"abc" * 1000).hexdigest()


def test_flat_points_parses_polylines_as_lat_lon():
    lat, lon, off, lens = prepare.flat_points(["[[-8.6,41.1],[-8.5,41.2]]", "[]", "[[-8.4,41.3]]"])
    assert lat.tolist() == pytest.approx([41.1, 41.2, 41.3]) and lon.tolist() == pytest.approx([-8.6, -8.5, -8.4])
    assert off.tolist() == [0, 2, 2, 3] and lens.tolist() == [2, 0, 1]
    with pytest.raises(ValueError):
        prepare.flat_points(["[[-8.6,41.1],[-8.5]]"])


def test_table_codes_the_columns():
    df = pd.DataFrame({"TRIP_ID": [1, 2], "CALL_TYPE": ["A", "C"], "ORIGIN_CALL": [123.0, np.nan],
                       "ORIGIN_STAND": [np.nan, 15.0], "TAXI_ID": [20000001, 20000002],
                       "TIMESTAMP": [1372636800, 1372636801], "DAY_TYPE": ["A", "A"],
                       "MISSING_DATA": ["False", "TRUE"], "POLYLINE": ["[[-8.6,41.1]]", "[]"]})
    t = prepare.table(df)
    assert t["trip_id"].tolist() == ["1", "2"] and t["call_type"].tolist() == [0, 2]
    assert t["origin_call"].tolist() == [123, 0] and t["origin_stand"].tolist() == [0, 15]
    assert t["missing"].tolist() == [False, True] and t["lens"].tolist() == [1, 0]

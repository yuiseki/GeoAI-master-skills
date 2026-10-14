"""uvx --with duckdb --with scikit-learn --with pyarrow --with pytest pytest test_make_folds.py"""

import math

import numpy as np
import pytest

from make_folds import make_folds


def haversine_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def by_fold(rows):
    """{(repeat, fold): {"train": set(ids), "test": set(ids)}}"""
    out = {}
    for repeat, fold, rid, role in rows:
        out.setdefault((repeat, fold), {"train": set(), "test": set()})[role].add(rid)
    return out


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    n = 300
    return {
        "id": np.array([f"r{i}" for i in range(n)]),
        "group": np.array([f"g{i % 12}" for i in range(n)]),
        "y": (rng.uniform(size=n) < 0.2).astype(int),
        "lon": rng.uniform(-30, 30, size=n),
        "lat": rng.uniform(40, 70, size=n),
        "time": rng.integers(2010, 2020, size=n),
    }


def test_rows_test_each_row_once_per_repeat(data):
    rows = make_folds(data["id"], scheme="rows", folds=5, repeats=[0, 1])
    folds = by_fold(rows)
    for repeat in (0, 1):
        tested = [i for (r, _), f in folds.items() if r == repeat for i in f["test"]]
        assert sorted(tested) == sorted(data["id"])
    for f in folds.values():
        assert f["train"] | f["test"] == set(data["id"])
        assert not f["train"] & f["test"]


def test_stratified_keeps_the_class_share(data):
    rows = make_folds(data["id"], scheme="stratified", folds=5, repeats=[0], target=data["y"])
    y = dict(zip(data["id"], data["y"]))
    share = data["y"].mean()
    for f in by_fold(rows).values():
        assert np.mean([y[i] for i in f["test"]]) == pytest.approx(share, abs=0.03)


def test_group_keeps_each_group_on_one_side(data):
    g = dict(zip(data["id"], data["group"]))
    for f in by_fold(make_folds(data["id"], scheme="group", folds=4, repeats=[0],
                                group=data["group"])).values():
        assert not {g[i] for i in f["train"]} & {g[i] for i in f["test"]}


def test_spatial_blocks_with_buffer_leave_no_training_row_near_a_test_row(data):
    pos = {i: (x, y) for i, x, y in zip(data["id"], data["lon"], data["lat"])}
    rows = make_folds(data["id"], scheme="spatial-block", folds=5, repeats=[0],
                      lon=data["lon"], lat=data["lat"], block_km=500, buffer_km=150)
    for f in by_fold(rows).values():
        assert f["test"]
        for t in f["test"]:
            for r in f["train"]:
                assert haversine_km(*pos[t], *pos[r]) > 150


def test_spatial_blocks_are_whole(data):
    # A block is all on one side: two rows 1 km apart (same block) are never split.
    ids = np.array(["a", "b", "c"])
    lon = np.array([10.0, 10.01, -20.0])
    lat = np.array([60.0, 60.0, 45.0])
    for repeat in range(5):
        for f in by_fold(make_folds(ids, scheme="spatial-block", folds=2, repeats=[repeat],
                                    lon=lon, lat=lat, block_km=500, buffer_km=0)).values():
            assert {"a", "b"} <= f["test"] or not {"a", "b"} & f["test"]


def test_time_never_trains_on_the_test_period_or_later(data):
    t = dict(zip(data["id"], data["time"]))
    rows = make_folds(data["id"], scheme="time", folds=3, repeats=[0], time=data["time"], gap=1)
    folds = by_fold(rows)
    assert sorted({t[i] for f in folds.values() for i in f["test"]}) == [2017, 2018, 2019]
    for f in folds.values():
        period = {t[i] for i in f["test"]}
        assert len(period) == 1
        (p,) = period
        assert max(t[i] for i in f["train"]) < p - 1  # gap of one period


def test_space_time_combines_both(data):
    t = dict(zip(data["id"], data["time"]))
    pos = {i: (x, y) for i, x, y in zip(data["id"], data["lon"], data["lat"])}
    rows = make_folds(data["id"], scheme="space-time", folds=3, repeats=[0], time=data["time"],
                      gap=0, lon=data["lon"], lat=data["lat"], block_km=500, buffer_km=150,
                      space_folds=4)
    for f in by_fold(rows).values():
        if not f["test"]:
            continue
        (p,) = {t[i] for i in f["test"]}
        assert max(t[i] for i in f["train"]) < p
        for a in f["test"]:
            for b in f["train"]:
                assert haversine_km(*pos[a], *pos[b]) > 150


def test_the_command_line_writes_a_fold_table_score_folds_can_read(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    import duckdb

    here = Path(__file__).parent
    table, folds = tmp_path / "t.parquet", tmp_path / "folds.parquet"
    duckdb.sql(f"""
        copy (select 'r' || i as id, i % 4 as g, (i * 7) % 10 as y,
                     -20 + (i * 13) % 40 as lon, 40 + (i * 17) % 30 as lat, 2000 + i % 6 as year
              from range(60) t(i)) to '{table}' (format parquet)
    """)
    for args in (["--scheme", "rows"], ["--scheme", "group", "--group", "g", "--folds", "4"],
                 ["--scheme", "spatial-block", "--lon", "lon", "--lat", "lat", "--block-km", "800",
                  "--buffer-km", "100"],
                 ["--scheme", "time", "--time", "year", "--folds", "2"]):
        r = subprocess.run([sys.executable, str(here / "make_folds.py"), str(table), "id", *args,
                        "--out", str(folds)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        rows = duckdb.sql(f"select repeat, fold, id, role from '{folds}'").fetchall()
        assert rows and {r[3] for r in rows} == {"train", "test"}

    sys.path.insert(0, str(here))
    from score_folds import load_folds

    ids = duckdb.sql(f"select id from '{table}'").fetchnumpy()["id"]
    loaded = load_folds(str(folds), ids)
    assert len(loaded[0]) == 2

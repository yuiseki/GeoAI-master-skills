"""Make one fold table that every baseline and model is then scored on.

The fold table has one row per (repeat, fold, id) that takes part in that fold, with role 'train' or
'test'. A row absent from a fold is not used in it: in time folds, rows of the test period or later
are not trained on; with a spatial buffer, training rows near a test row are left out.

Schemes:
    rows           shuffled K-fold; every row is tested once per repeat
    stratified     as rows, keeping the share of each class of --target in every fold
    group          whole groups of --group held out (the repeat does not change the folds)
    spatial-block  blocks of about --block-km square held out, training rows within --buffer-km of a
                   test row left out; blocks are shuffled into folds by the repeat
    time           each of the last --folds periods of --time tested in turn, trained on periods
                   before it minus --gap
    space-time     time folds crossed with --space-folds spatial-block folds: test rows of one
                   period and one block fold, trained on earlier periods outside those blocks and
                   the buffer

Usage:
    uvx --with duckdb --with scikit-learn --with pyarrow python make_folds.py TABLE ID_COLUMN \
        --scheme SCHEME [--folds 5] [--repeats 0 1 2] [--group COL] [--target COL] \
        [--lon COL --lat COL | --geometry COL] [--block-km 500] [--buffer-km 0] \
        [--time COL] [--gap 0] [--space-folds 5] --out folds.parquet
"""

import argparse
import math

import duckdb
import numpy as np
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.neighbors import BallTree

EARTH_KM = 6371.0


def spatial_blocks(lon, lat, block_km):
    """Block key per row on a grid of nearly equal-area cells about block_km on a side.

    Latitude bands are block_km tall; each band is cut into as many cells as fit its length of
    parallel at the band's middle, so cells do not narrow towards the poles.
    """
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    km_per_deg = math.pi * EARTH_KM / 180
    band_deg = block_km / km_per_deg
    band = np.floor((lat + 90) / band_deg).astype(int)
    mid = np.radians(np.clip(-90 + (band + 0.5) * band_deg, -90, 90))
    cells = np.maximum(1, np.round(2 * math.pi * EARTH_KM * np.cos(mid) / block_km)).astype(int)
    col = np.floor((lon + 180) / 360 * cells).astype(int) % cells
    return np.array([f"{b}:{c}" for b, c in zip(band, col)])


def blocks_to_folds(blocks, folds, seed):
    """Shuffle the blocks and give each to the fold with the fewest rows so far."""
    keys, counts = np.unique(blocks, return_counts=True)
    order = np.random.default_rng(seed).permutation(len(keys))
    size = np.zeros(folds, int)
    fold_of = {}
    for k in order:
        f = int(np.argmin(size))
        fold_of[keys[k]] = f
        size[f] += counts[k]
    if len(keys) < folds:
        raise SystemExit(f"{len(keys)} blocks for {folds} folds: make --block-km smaller")
    return np.array([fold_of[b] for b in blocks])


def outside_buffer(train, test, lon, lat, buffer_km):
    """The training indices farther than buffer_km from every test index."""
    if buffer_km <= 0 or len(test) == 0:
        return train
    # BallTree's haversine takes (latitude, longitude) in radians.
    tree = BallTree(np.radians(np.c_[lat[test], lon[test]]), metric="haversine")
    near = tree.query_radius(np.radians(np.c_[lat[train], lon[train]]), r=buffer_km / EARTH_KM,
                             count_only=True)
    return train[near == 0]


def make_folds(ids, scheme, folds, repeats, group=None, target=None, lon=None, lat=None,
               block_km=None, buffer_km=0.0, time=None, gap=0, space_folds=None):
    ids = np.asarray(ids)
    n = len(ids)
    if len(set(ids.tolist())) != n:
        raise SystemExit("the id column is not unique")
    if lon is not None:
        lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    rows = []

    def emit(repeat, fold, train, test):
        if len(test) == 0:
            return
        if len(train) == 0:
            raise SystemExit(f"repeat {repeat} fold {fold}: no training rows")
        rows.extend((repeat, fold, ids[i], "train") for i in train)
        rows.extend((repeat, fold, ids[i], "test") for i in test)

    def time_folds():
        t = np.asarray(time)
        periods = np.unique(t)
        if len(periods) <= folds:
            raise SystemExit(f"{len(periods)} periods for {folds} time folds")
        return t, periods[-folds:]

    for repeat in repeats:
        if scheme == "rows":
            splits = KFold(folds, shuffle=True, random_state=repeat).split(ids)
        elif scheme == "stratified":
            splits = StratifiedKFold(folds, shuffle=True, random_state=repeat).split(ids, target)
        elif scheme == "group":
            splits = GroupKFold(folds).split(ids, groups=group)
        elif scheme == "spatial-block":
            fold_of = blocks_to_folds(spatial_blocks(lon, lat, block_km), folds, repeat)
            splits = []
            for f in range(folds):
                test = np.flatnonzero(fold_of == f)
                train = outside_buffer(np.flatnonzero(fold_of != f), test, lon, lat, buffer_km)
                splits.append((train, test))
        elif scheme == "time":
            t, tested = time_folds()
            splits = [(np.flatnonzero(t < p - gap), np.flatnonzero(t == p)) for p in tested]
        elif scheme == "space-time":
            t, tested = time_folds()
            fold_of = blocks_to_folds(spatial_blocks(lon, lat, block_km), space_folds, repeat)
            splits = []
            for p in tested:
                for s in range(space_folds):
                    test = np.flatnonzero((t == p) & (fold_of == s))
                    train = np.flatnonzero((t < p - gap) & (fold_of != s))
                    splits.append((outside_buffer(train, test, lon, lat, buffer_km), test))
        else:
            raise SystemExit(f"unknown scheme {scheme}")
        for fold, (train, test) in enumerate(splits):
            emit(repeat, fold, np.asarray(train), np.asarray(test))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("--scheme", required=True,
                   choices=["rows", "stratified", "group", "spatial-block", "time", "space-time"])
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--repeats", type=int, nargs="+", default=[0, 1, 2])
    p.add_argument("--group")
    p.add_argument("--target")
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--geometry")
    p.add_argument("--block-km", type=float)
    p.add_argument("--buffer-km", type=float, default=0.0)
    p.add_argument("--time")
    p.add_argument("--gap", type=int, default=0)
    p.add_argument("--space-folds", type=int, default=5)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    cols = {"id": f'"{a.id}"'}
    for name, col in (("group", a.group), ("target", a.target), ("time", a.time)):
        if col:
            cols[name] = f'"{col}"'
    if a.geometry:
        pt = f'ST_PointOnSurface("{a.geometry}")'
        cols["lon"], cols["lat"] = f"ST_X({pt})", f"ST_Y({pt})"
    elif a.lon:
        cols["lon"], cols["lat"] = f'"{a.lon}"', f'"{a.lat}"'
    select = ", ".join(f"{v} as {k}" for k, v in cols.items())
    t = con.sql(f"select {select} from '{a.table}'").fetchnumpy()
    for k, v in t.items():
        if np.ma.isMaskedArray(v) and v.mask.any():
            raise SystemExit(f"{k} has {int(v.mask.sum())} missing values; drop those rows first")
    needs = {"stratified": ["target"], "group": ["group"], "spatial-block": ["lon"],
             "time": ["time"], "space-time": ["time", "lon"]}.get(a.scheme, [])
    for k in needs:
        if k not in t:
            raise SystemExit(f"--scheme {a.scheme} needs the {k} column")
    if a.scheme in ("spatial-block", "space-time") and not a.block_km:
        raise SystemExit("--block-km is required for spatial blocks")

    rows = make_folds(t["id"], a.scheme, a.folds, a.repeats, group=t.get("group"),
                      target=t.get("target"), lon=t.get("lon"), lat=t.get("lat"),
                      block_km=a.block_km, buffer_km=a.buffer_km, time=t.get("time"),
                      gap=a.gap, space_folds=a.space_folds)

    import pyarrow as pa

    fold_rows = pa.table({
        "repeat": [r[0] for r in rows],
        "fold": [r[1] for r in rows],
        "id": [r[2] for r in rows],
        "role": [r[3] for r in rows],
    })
    con.sql(f"copy (select * from fold_rows order by all) to '{a.out}' (format parquet)")
    n = len(t["id"])
    print(f"rows: {n}, scheme: {a.scheme}")
    if a.scheme in ("spatial-block", "space-time"):
        blocks = spatial_blocks(t["lon"], t["lat"], a.block_km)
        print(f"spatial blocks of about {a.block_km:g} km: {len(np.unique(blocks))}")
    for r in con.sql(f"""
        select repeat, fold, count(*) filter (where role = 'train') as train,
               count(*) filter (where role = 'test') as test,
               {n} - count(*) as unused
        from '{a.out}' group by all order by all
    """).fetchall():
        print("repeat {} fold {}: train {}, test {}, unused {}".format(*r))
    tested = con.sql(f"""
        select repeat, count(distinct id) from '{a.out}' where role = 'test' group by 1 order by 1
    """).fetchall()
    for repeat, k in tested:
        print(f"repeat {repeat}: {k} of {n} rows tested at least once")


if __name__ == "__main__":
    main()

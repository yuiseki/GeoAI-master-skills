"""Read the UCI files once into arrays: artifacts/.../trips.npz (train) and kaggle_test.npz (the 320 prefixes and their
destinations). Writes outputs/sources.csv (file, bytes, sha256) and outputs/prepare_counts.csv (rows read, kept, dropped).

  python3 scripts/prepare.py
"""

import csv
import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "artifacts/_benchmark/taxi-destination-porto/raw"
ART = RAW.parent
OUT = Path(__file__).resolve().parent.parent / "outputs"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def flat_points(polylines):
    """'[[lon,lat],...]' strings -> (lat, lon, offsets). Parsed as numbers without json for speed."""
    lens = np.empty(len(polylines), dtype=np.int64)
    parts = []
    for i, s in enumerate(polylines):
        v = np.array(s.replace("[", " ").replace("]", " ").replace(",", " ").split(), dtype="float64")
        if len(v) % 2:
            raise ValueError(f"odd number of coordinates in row {i}")
        lens[i] = len(v) // 2
        parts.append(v)
    xy = np.concatenate(parts).reshape(-1, 2) if parts else np.zeros((0, 2))
    off = np.concatenate([[0], np.cumsum(lens)])
    return xy[:, 1].astype("float32"), xy[:, 0].astype("float32"), off, lens


def table(df):
    lat, lon, off, lens = flat_points(df["POLYLINE"].tolist())
    return dict(
        trip_id=df["TRIP_ID"].astype(str).to_numpy(),
        call_type=df["CALL_TYPE"].map({"A": 0, "B": 1, "C": 2}).to_numpy(np.int8),
        origin_call=df["ORIGIN_CALL"].fillna(0).astype(np.int64).to_numpy(),
        origin_stand=df["ORIGIN_STAND"].fillna(0).astype(np.int64).to_numpy(),
        taxi_id=df["TAXI_ID"].astype(np.int64).to_numpy(),
        timestamp=df["TIMESTAMP"].astype(np.int64).to_numpy(),
        day_type=df["DAY_TYPE"].map({"A": 0, "B": 1, "C": 2}).to_numpy(np.int8),
        missing=(df["MISSING_DATA"].astype(str).str.upper() == "TRUE").to_numpy(),
        lat=lat, lon=lon, off=off, lens=lens,
    )


def main():
    OUT.mkdir(exist_ok=True)
    z = zipfile.ZipFile(RAW / "uci339.zip")
    names = z.namelist()
    print(names)
    rows = [dict(file="uci339.zip", bytes=(RAW / "uci339.zip").stat().st_size, sha256=sha(RAW / "uci339.zip"))]
    for n in names:
        with z.open(n) as f:
            h = hashlib.sha256()
            size = 0
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
                size += len(b)
        rows.append(dict(file=n, bytes=size, sha256=h.hexdigest()))
    with open(OUT / "sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def read_csv(name):
        member = next(n for n in names if n.endswith(name))
        data = z.read(member)
        if member.endswith(".zip"):
            inner = zipfile.ZipFile(io.BytesIO(data))
            data = inner.read(inner.namelist()[0])
        return pd.read_csv(io.BytesIO(data), dtype={"TRIP_ID": str})

    counts = []
    test = read_csv("Porto_taxi_data_test_partial_trajectories.csv")
    sol = read_csv("solution_fixed.csv")
    print(sol.head(), sol.columns.tolist())
    t = table(test)
    s = sol.set_index(sol.columns[0]).loc[t["trip_id"]]
    t["dest_lat"] = s["LATITUDE"].to_numpy("float64")
    t["dest_lon"] = s["LONGITUDE"].to_numpy("float64")
    if "Usage" in s.columns:
        t["usage"] = s["Usage"].astype(str).to_numpy()
    np.savez(ART / "kaggle_test.npz", **t)
    counts.append(dict(table="kaggle_test", rows=len(test), kept=len(test), no_points=int((t["lens"] == 0).sum()),
                       missing_data=int(t["missing"].sum())))

    # train.csv is ~1.9 GB inside a nested zip: stream it in chunks
    inner = zipfile.ZipFile(io.BytesIO(z.read(next(n for n in names if n.endswith("train.csv.zip")))))
    chunks, rows = [], 0
    with inner.open(inner.namelist()[0]) as f:
        for df in pd.read_csv(f, dtype={"TRIP_ID": str}, chunksize=100000):
            rows += len(df)
            chunks.append(table(df))
            print(rows, flush=True)
    t = {k: np.concatenate([c[k] for c in chunks]) for k in chunks[0] if k != "off"}
    keep = t["lens"] > 0
    counts.append(dict(table="train", rows=rows, kept=int(keep.sum()), no_points=int((~keep).sum()),
                       missing_data=int(t["missing"].sum())))
    mask = np.repeat(keep, t["lens"])
    out = {k: v[keep] for k, v in t.items() if k not in ("lat", "lon")}
    out["lat"], out["lon"] = t["lat"][mask], t["lon"][mask]
    out["off"] = np.concatenate([[0], np.cumsum(out["lens"])])
    np.savez(ART / "trips.npz", **out)
    with open(OUT / "prepare_counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(counts[0]))
        w.writeheader()
        w.writerows(counts)
    print(counts)
    print("time range", pd.to_datetime(out["timestamp"].min(), unit="s"), pd.to_datetime(out["timestamp"].max(), unit="s"))


if __name__ == "__main__":
    main()

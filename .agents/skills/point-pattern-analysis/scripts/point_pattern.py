"""Are points closer together than a baseline distribution of places would put them?

For each radius r, the statistic is the number of pairs of points within r km of each other
(great-circle, sphere of radius 6,371 km), a form of Ripley's K. The same number of points is
placed --simulations times at random according to a baseline raster, and the observed count is
compared with the simulated ones: their median, a 95% envelope, and the ratio observed / median.
Because simulated points are placed in the same raster, edge effects affect both sides alike and
need no correction.

Baselines (from one GeoTIFF in EPSG:4326, cells with nodata or a value <= 0 excluded):
    values  a cell is chosen in proportion to its value (population: "where people live")
    area    a cell is chosen in proportion to its area (cos latitude): "anywhere in the window"
A point is placed uniformly within its cell.

Usage:
    env -u GDAL_DATA -u PROJ_DATA -u GDAL_DRIVER_PATH uvx --with numpy --with scipy --with rasterio \
        --with duckdb python point_pattern.py POINTS RASTER [--where SQL] \
        --baseline values|area --radii 5 10 20 50 [--simulations 99]
    ... python point_pattern.py POINTS --marks COL --type-a A --type-b B --radii 5 10 20 [--simulations 99]

With --marks, the pairs between type A and type B are compared with random labelling: the positions of all the
selected points stay and their types are shuffled. It asks whether the two types sit closer (or farther) than
if they came from one process; it does not ask whether the points cluster.

POINTS is anything DuckDB reads with a point geometry column, or --lon/--lat columns.
"""

import argparse
import math

import numpy as np
import rasterio
from scipy.spatial import cKDTree

EARTH_KM = 6371.0


def _xyz(lon, lat):
    lon, lat = np.radians(lon), np.radians(lat)
    return np.c_[np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]


def _chord(km):
    return 2 * np.sin(np.asarray(km, float) / EARTH_KM / 2)


def pair_counts(lon, lat, radii_km):
    """Unordered pairs of distinct points within each radius (great-circle km)."""
    tree = cKDTree(_xyz(np.asarray(lon, float), np.asarray(lat, float)))
    ordered = tree.count_neighbors(tree, _chord(radii_km))
    n = len(lon)
    return (np.asarray(ordered) - n) // 2  # drop self-pairs, count each pair once


def cross_pair_counts(lon, lat, marks, a, b, radii_km):
    """Pairs (one point of type a, one of type b) within each radius (great-circle km)."""
    lon, lat, marks = np.asarray(lon, float), np.asarray(lat, float), np.asarray(marks)
    ia, ib = marks == a, marks == b
    ta, tb = cKDTree(_xyz(lon[ia], lat[ia])), cKDTree(_xyz(lon[ib], lat[ib]))
    return np.asarray(ta.count_neighbors(tb, _chord(radii_km)))


def cross_label_test(lon, lat, marks, a, b, radii, simulations=99, seed=0):
    """Cross pair counts against random labelling: the positions stay, the marks are shuffled. It asks whether
    the two types sit closer together (or farther apart) than if they came from one process; a background both
    types follow (population, roads) shows in both sides alike."""
    marks = np.asarray(marks)
    obs = cross_pair_counts(lon, lat, marks, a, b, radii)
    rng = np.random.default_rng(seed)
    sims = np.array([cross_pair_counts(lon, lat, rng.permutation(marks), a, b, radii) for _ in range(simulations)])
    out = []
    for i, r in enumerate(radii):
        s = sims[:, i]
        med = float(np.median(s))
        out.append({"r_km": float(r), "observed": int(obs[i]), "median": med,
                    "low": float(np.percentile(s, 2.5)), "high": float(np.percentile(s, 97.5)),
                    "ratio": float(obs[i] / med) if med > 0 else math.inf,
                    "p_more": (int((s >= obs[i]).sum()) + 1) / (simulations + 1),
                    "p_less": (int((s <= obs[i]).sum()) + 1) / (simulations + 1)})
    return {"n_a": int((marks == a).sum()), "n_b": int((marks == b).sum()), "radii": out}


class Baseline:
    def __init__(self, path, weights="values"):
        with rasterio.open(path) as r:
            if r.crs is None or r.crs.to_epsg() != 4326:
                raise SystemExit(f"{path}: the raster must be in EPSG:4326, not {r.crs}")
            a = r.read(1, masked=True)
            self.transform = r.transform
            self.shape = a.shape
        values = np.ma.filled(a.astype(float), 0.0)
        rows, cols = np.nonzero(values > 0)
        if len(rows) == 0:
            raise SystemExit(f"{path}: no cell has a value above 0")
        self.rows, self.cols = rows, cols
        self.valid = np.zeros(self.shape, bool)
        self.valid[rows, cols] = True
        t = self.transform
        self.dx, self.dy = t.a, -t.e
        lat_centre = t.f + t.e * (rows + 0.5)
        if weights == "values":
            w = values[rows, cols]
        elif weights == "area":
            w = np.cos(np.radians(lat_centre))
        else:
            raise SystemExit(f"unknown weights {weights}")
        self.p = w / w.sum()

    def sample(self, n, rng):
        k = rng.choice(len(self.p), size=n, p=self.p)
        t = self.transform
        west = t.c + t.a * self.cols[k]
        north = t.f + t.e * self.rows[k]
        lon = west + rng.uniform(0, self.dx, n)
        # Uniform in area within the cell: uniform in sin(latitude).
        s_north, s_south = np.sin(np.radians(north)), np.sin(np.radians(north - self.dy))
        lat = np.degrees(np.arcsin(rng.uniform(s_south, s_north)))
        return lon, lat

    def outside(self, lon, lat):
        """Number of points that fall in no cell the baseline can place a point in."""
        t = self.transform
        col = np.floor((np.asarray(lon) - t.c) / t.a).astype(int)
        row = np.floor((np.asarray(lat) - t.f) / t.e).astype(int)
        inside = (row >= 0) & (row < self.shape[0]) & (col >= 0) & (col < self.shape[1])
        ok = np.zeros(len(col), bool)
        ok[inside] = self.valid[row[inside], col[inside]]
        return int((~ok).sum())


def pattern_test(lon, lat, baseline, radii, simulations=99, seed=0):
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    obs = pair_counts(lon, lat, radii)
    rng = np.random.default_rng(seed)
    sims = np.array([pair_counts(*baseline.sample(len(lon), rng), radii)
                     for _ in range(simulations)])
    out = []
    for i, r in enumerate(radii):
        s = sims[:, i]
        med = float(np.median(s))
        more = int((s >= obs[i]).sum())
        out.append({"r_km": float(r), "observed": int(obs[i]), "median": med,
                    "low": float(np.percentile(s, 2.5)), "high": float(np.percentile(s, 97.5)),
                    "ratio": float(obs[i] / med) if med > 0 else math.inf,
                    "p_more_clustered": (more + 1) / (simulations + 1),
                    "p_more_dispersed": (int((s <= obs[i]).sum()) + 1) / (simulations + 1)})
    return {"n": len(lon), "radii": out}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("points")
    p.add_argument("raster", nargs="?", help="the baseline raster (not needed with --marks)")
    p.add_argument("--where", default="true")
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--baseline", choices=["values", "area"])
    p.add_argument("--marks", help="a column of point types: cross pairs of --type-a and --type-b against random "
                                    "labelling (no raster)")
    p.add_argument("--type-a")
    p.add_argument("--type-b")
    p.add_argument("--radii", type=float, nargs="+", required=True)
    p.add_argument("--simulations", type=int, default=99)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    import duckdb

    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    xy = (f'"{a.lon}" as lon, "{a.lat}" as lat' if a.lon
          else "ST_X(geometry) as lon, ST_Y(geometry) as lat")
    mk = f', cast("{a.marks}" as varchar) as mark' if a.marks else ""
    t = con.sql(f"select {xy}{mk} from '{a.points}' where {a.where}").fetchnumpy()
    lon, lat = np.asarray(t["lon"], float), np.asarray(t["lat"], float)
    if a.marks:
        if not (a.type_a and a.type_b):
            p.error("--marks needs --type-a and --type-b")
        marks = np.asarray(t["mark"]).astype(str)
        r = cross_label_test(lon, lat, marks, a.type_a, a.type_b, a.radii, a.simulations, a.seed)
        print(f"points: {len(lon)}; {a.type_a} {r['n_a']}, {a.type_b} {r['n_b']}, other types {len(lon) - r['n_a'] - r['n_b']} "
              f"(kept in the shuffle); random labelling, {a.simulations} shuffles")
        print("r (km): cross pairs observed, shuffled median [95% envelope], ratio, p (more), p (fewer)")
        for row in r["radii"]:
            print(f"  {row['r_km']:>7g}: {row['observed']:>9} {row['median']:>11.0f} "
                  f"[{row['low']:.0f}, {row['high']:.0f}]  {row['ratio']:.2f}  {row['p_more']:.3f}  {row['p_less']:.3f}")
        return
    if not (a.raster and a.baseline):
        p.error("give a baseline raster and --baseline, or --marks")
    base = Baseline(a.raster, a.baseline)
    out = base.outside(lon, lat)
    print(f"points: {len(lon)} ({out} in no baseline cell, kept), baseline: {a.baseline}, "
          f"simulations: {a.simulations}")
    r = pattern_test(lon, lat, base, a.radii, a.simulations, a.seed)
    print("r (km): pairs observed, simulated median [95% envelope], ratio, p (more clustered), p (more dispersed)")
    for row in r["radii"]:
        print(f"  {row['r_km']:>7g}: {row['observed']:>9} {row['median']:>11.0f} "
              f"[{row['low']:.0f}, {row['high']:.0f}]  {row['ratio']:.2f}  {row['p_more_clustered']:.3f}  "
              f"{row['p_more_dispersed']:.3f}")


if __name__ == "__main__":
    main()

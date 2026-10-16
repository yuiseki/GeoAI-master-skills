"""Measure how identifiable point locations stay after a protection, and what the protection costs.

These are attack simulations, not guarantees. A protection that passes one attack can fail another (a
road network, a building layer, a second release of the same data). Coordinates are projected metres.

    cell_counts             counts in square cells; cells with fewer than min_count points are suppressed
                            (None, not 0), with how many cells and points were hidden and how many cells
                            held exactly one point
    donut_mask              move each point in a random direction by a distance between r_min and r_max,
                            uniform in area (donut geomasking)
    nearest_candidate_hits  for each masked point, is the nearest candidate (house, address) the true one?
    candidates_within       how many candidates lie within a radius of each masked point (spatial k)
    adaptive_donut          a donut whose outer radius is each point's distance to its k-th nearest
                            candidate (the point's own house counted) and whose inner radius is a share of it:
                            small in dense places, large in sparse ones, so every point's annulus holds at
                            least k - 1 other candidates around its true location (Allshouse et al. 2010)
    average_releases        the mean of several independent maskings of the same points
    home_location           the most frequent night-time cell of a trace, and its centre

Usage (as a module, or for one table of points):
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python privacy_check.py POINTS X Y \\
        --candidates HOUSES --cx X --cy Y --cell 500 --min-count 5 --r-min 50 --r-max 200 [--seed 0]
"""

import argparse

import numpy as np
from scipy.spatial import cKDTree


def cell_counts(xy, cell, min_count):
    keys = [tuple(k) for k in np.floor(np.asarray(xy, float) / cell).astype(int).tolist()]
    raw = {}
    for k in keys:
        raw[k] = raw.get(k, 0) + 1
    counts = {k: (v if v >= min_count else None) for k, v in raw.items()}
    hidden = [v for v in raw.values() if v < min_count]
    return {"counts": counts, "suppressed_cells": len(hidden), "suppressed_points": int(sum(hidden)),
            "unique_cells": sum(1 for v in raw.values() if v == 1), "cells": len(raw)}


def donut_mask(xy, r_min, r_max, seed=0):
    xy = np.asarray(xy, float)
    rng = np.random.default_rng(seed)
    r = np.sqrt(rng.uniform(r_min**2, r_max**2, len(xy)))
    a = rng.uniform(0, 2 * np.pi, len(xy))
    return xy + np.c_[r * np.cos(a), r * np.sin(a)]


def adaptive_radii(xy, candidates, k, inner=0.2):
    """Per point: (inner radius, outer radius), the outer one the distance to the k-th nearest candidate."""
    d, _ = cKDTree(np.asarray(candidates, float)).query(np.asarray(xy, float), k)
    r_out = np.asarray(d, float).reshape(len(xy), -1)[:, -1]
    return inner * r_out, r_out


def adaptive_donut(xy, candidates, k, inner=0.2, seed=0):
    xy = np.asarray(xy, float)
    r_in, r_out = adaptive_radii(xy, candidates, k, inner)
    rng = np.random.default_rng(seed)
    r = np.sqrt(r_in ** 2 + rng.random(len(xy)) * (r_out ** 2 - r_in ** 2))
    a = rng.uniform(0, 2 * np.pi, len(xy))
    return xy + np.c_[r * np.cos(a), r * np.sin(a)], r_out


def nearest_candidate_hits(masked, candidates, true_index):
    _, idx = cKDTree(np.asarray(candidates, float)).query(np.asarray(masked, float))
    return [bool(i == t) for i, t in zip(idx, true_index)]


def candidates_within(masked, candidates, radius):
    tree = cKDTree(np.asarray(candidates, float))
    return np.array([len(x) for x in tree.query_ball_point(np.asarray(masked, float), radius)])


def average_releases(xy, r_min, r_max, releases, seed=0):
    return np.mean([donut_mask(xy, r_min, r_max, seed=seed + i) for i in range(releases)], axis=0)


def home_location(xy, hours, cell, night=(22, 6)):
    xy = np.asarray(xy, float)
    h = np.asarray(hours)
    at_night = (h >= night[0]) | (h < night[1])
    keys = [tuple(k) for k in np.floor(xy[at_night] / cell).astype(int).tolist()]
    if not keys:
        return {"cell": None, "night_points": 0, "xy": None}
    best = max(set(keys), key=keys.count)
    return {"cell": best, "night_points": len(keys), "xy": ((best[0] + 0.5) * cell, (best[1] + 0.5) * cell)}


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("points")
    p.add_argument("x")
    p.add_argument("y")
    p.add_argument("--candidates", help="table of possible true locations (houses, addresses)")
    p.add_argument("--cx")
    p.add_argument("--cy")
    p.add_argument("--cell", type=float, required=True)
    p.add_argument("--min-count", type=int, default=5)
    p.add_argument("--r-min", type=float, required=True)
    p.add_argument("--r-max", type=float, required=True)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    pts = np.array(duckdb.sql(f'select "{a.x}", "{a.y}" from \'{a.points}\'').fetchall(), float)
    c = cell_counts(pts, a.cell, a.min_count)
    print(f"points {len(pts)}, cells {c['cells']}, cells with one point {c['unique_cells']}, "
          f"suppressed below {a.min_count}: {c['suppressed_cells']} cells, {c['suppressed_points']} points")
    if a.candidates:
        cand = np.array(duckdb.sql(f'select "{a.cx}", "{a.cy}" from \'{a.candidates}\'').fetchall(), float)
        _, true = cKDTree(cand).query(pts)
        exact = np.mean(nearest_candidate_hits(pts, cand, true))
        m = donut_mask(pts, a.r_min, a.r_max, a.seed)
        hit = np.mean(nearest_candidate_hits(m, cand, true))
        k = candidates_within(m, cand, a.r_max)
        print(f"nearest candidate is the true one: exact {exact:.1%}, masked {hit:.1%}")
        print(f"candidates within {a.r_max:g} m of a masked point: median {np.median(k):.0f}, "
              f"fewer than 5 for {np.mean(k < 5):.1%} of points")


if __name__ == "__main__":
    main()

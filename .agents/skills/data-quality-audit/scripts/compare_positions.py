"""Compare where two sources put the same features: match by a key, measure the distance between them.

Each feature on the left is matched to the right-hand features with the same key; when there are several
candidates, the nearest is taken and the left feature is counted as having several. Distances are
great-circle (sphere of radius 6,371 km) in metres, from longitude and latitude columns.

Prints: rows on each side, rows with a missing coordinate, matched, unmatched on each side (with the keys),
left features with several candidates, and the distances: median, p90, p95, max, RMSE, and the share over
each --radii value. With no reference of known accuracy this is agreement between two sources, not the
accuracy of either: each one's error is part of the distance.

Usage:
    uvx --from 'duckdb>=1.5.5' python compare_positions.py LEFT RIGHT KEY [--lon lon --lat lat]
        [--right-key KEY] [--right-lon COL --right-lat COL] [--radii 50 100 200]
"""

import argparse
import math

import duckdb

R = 6371000.0


def _dist(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def _rows(path, key, lon, lat):
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs;")
    return con.sql(f'select "{key}", "{lon}", "{lat}" from \'{path}\'').fetchall()


def compare(left, right, key, lon="lon", lat="lat", right_key=None, right_lon=None, right_lat=None, radii=(50, 100, 200)):
    L = _rows(left, key, lon, lat)
    Rr = _rows(right, right_key or key, right_lon or lon, right_lat or lat)
    rep = {"left_rows": len(L), "right_rows": len(Rr),
           "missing_coordinates_left": sum(r[1] is None or r[2] is None for r in L),
           "missing_coordinates_right": sum(r[1] is None or r[2] is None for r in Rr)}
    cand = {}
    for k, x, y in Rr:
        if x is not None and y is not None:
            cand.setdefault(k, []).append((float(x), float(y)))
    dists, unmatched, several, matched_keys = [], [], 0, set()
    for k, x, y in L:
        if x is None or y is None:
            continue
        c = cand.get(k)
        if not c:
            unmatched.append(k)
            continue
        several += len(c) > 1
        dists.append(min(_dist(float(x), float(y), cx, cy) for cx, cy in c))
        matched_keys.add(k)
    left_keys = {r[0] for r in L}
    rep.update(matched=len(dists), unmatched_left=unmatched,
               unmatched_right=sorted(k for k in cand if k not in left_keys),
               left_with_several_candidates=several, distances=dists)
    if dists:
        s = sorted(dists)
        q = lambda p: s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
        rep.update(median_m=q(0.5), p90_m=q(0.9), p95_m=q(0.95), max_m=s[-1],
                   rmse_m=math.sqrt(sum(d * d for d in s) / len(s)),
                   share_over={r: sum(d > r for d in s) / len(s) for r in radii})
    return rep


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("left")
    p.add_argument("right")
    p.add_argument("key")
    p.add_argument("--lon", default="lon")
    p.add_argument("--lat", default="lat")
    p.add_argument("--right-key")
    p.add_argument("--right-lon")
    p.add_argument("--right-lat")
    p.add_argument("--radii", type=float, nargs="+", default=[50, 100, 200])
    a = p.parse_args()
    r = compare(a.left, a.right, a.key, a.lon, a.lat, a.right_key, a.right_lon, a.right_lat, a.radii)
    for k, v in r.items():
        if k != "distances":
            print(f"{k}: {v[:20] if isinstance(v, list) else v}")


if __name__ == "__main__":
    main()

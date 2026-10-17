"""Score predicted points against answer points: one-to-one matching within a radius in metres.

    python score_points.py predictions.csv truth.csv --radius 100

predictions.csv has lon and lat columns (or longitude and latitude), WGS84 degrees, one point per row.
truth.csv has id, lon, lat. Pairs closer than the radius are taken closest first, and each prediction and each
answer point is used at most once, so two predictions on the same answer point count once. Distances are
great-circle (haversine), which is well within a metre of the geodesic at 100 m. Prints JSON: counts,
precision, recall, F1 and the ids of the answer points no prediction reached.
"""

import argparse
import csv
import json
import math
import sys

R_EARTH = 6_371_008.8


def haversine_m(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(h))


def match(preds, truth, radius_m):
    pairs = sorted((d, i, j) for i, p in enumerate(preds) for j, (_, x, y) in enumerate(truth)
                   if (d := haversine_m(p, (x, y))) <= radius_m)
    used_p, used_t = set(), set()
    for _, i, j in pairs:
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
    m = len(used_t)
    precision = m / len(preds) if preds else 0.0
    recall = m / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"radius_m": radius_m, "n_pred": len(preds), "n_truth": len(truth), "matched": m,
            "precision": precision, "recall": recall, "f1": f1,
            "missed": [truth[j][0] for j in range(len(truth)) if j not in used_t]}


def read_points(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    keys = {k.strip().lower(): k for k in rows[0]}
    lon = keys.get("lon") or keys.get("longitude")
    lat = keys.get("lat") or keys.get("latitude")
    if not lon or not lat:
        raise SystemExit(f"{path}: needs lon and lat columns, has {list(rows[0])}")
    pts = [(float(r[lon]), float(r[lat])) for r in rows]
    bad = [p for p in pts if not (122 <= p[0] <= 154 and 20 <= p[1] <= 46)]
    if bad:
        raise SystemExit(f"{path}: {len(bad)} points outside Japan, such as {bad[0]}; lon and lat swapped?")
    return pts


def read_truth(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [(r["id"], float(r["lon"]), float(r["lat"])) for r in csv.DictReader(f)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("predictions")
    p.add_argument("truth")
    p.add_argument("--radius", type=float, default=100)
    a = p.parse_args()
    r = match(read_points(a.predictions), read_truth(a.truth), a.radius)
    r["radius_m"] = int(a.radius) if a.radius.is_integer() else a.radius
    json.dump(r, sys.stdout, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()

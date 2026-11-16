"""Before reading "not detected" as "not there": would the object be in a view at all, large enough, and not hidden?

For each target (a pole from OSM or a register, in a projected CRS in metres) and each level view (pitch 0, as
equirect_view.py cuts them), this computes the angle off the view's axis, the depth along the axis, and the rows of
the target's foot and top on flat ground:

    f = (width / 2) / tan(hfov / 2)       depth = distance * cos(angle off the axis)
    foot row = height / 2 + f * camera_height / depth
    top row  = height / 2 - f * (target_height - camera_height) / depth

The target counts as should_be_visible in a view when it is inside the horizontal angle of view, no farther than
--max-distance, at least --min-px tall in the frame (by default 15% of the view's height, the smallest box
inspect_views.py keeps as a pole), and no occluder (building footprints) crosses the sight line from the camera to it.
Otherwise the view gives reasons: out_of_frame, too_far, too_small, occluded. Only targets that some view should
show can count as missed by the detector; the others say nothing about whether the object is there.

Assumptions: flat ground, a level camera at a known height (2.5 m for a car roof), the target's height. A slope,
a tilted camera or a wrong height moves the rows. Trees, parked vehicles and people are not occluders here.

    python3 expected_view.py views.csv poles.csv --target-height 8 [--occluders buildings.geojson] \
        [--detected detected.csv] --out expected.csv
views.csv: view_id, x, y, azimuth (degrees clockwise from grid north), hfov, width, height.
poles.csv: id, x, y [, height]. detected.csv: id (targets the detector matched). All coordinates in one projected CRS.
"""

import argparse
import csv
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass

PRIORITY = {"occluded": 1, "too_small": 2, "too_far": 3, "out_of_frame": 4}


@dataclass
class View:
    x: float
    y: float
    azimuth: float
    hfov: float
    width: int
    height: int
    camera_height: float = 2.5
    view_id: str = ""


def expect(view, x, y, target_height, min_px=None, max_distance=None, occluders=()):
    dx, dy = x - view.x, y - view.y
    dist = math.hypot(dx, dy)
    bearing = math.degrees(math.atan2(dx, dy)) % 360
    off = (bearing - view.azimuth + 180) % 360 - 180
    r = {"distance": dist, "off_axis": off, "reasons": []}
    if dist == 0 or abs(off) > view.hfov / 2:
        r.update(verdict="not_visible", reasons=["out_of_frame"])
        return r
    f = (view.width / 2) / math.tan(math.radians(view.hfov) / 2)
    depth = dist * math.cos(math.radians(off))
    c = view.height / 2
    foot = c + f * view.camera_height / depth
    top = c - f * (target_height - view.camera_height) / depth
    px = max(0.0, min(foot, view.height) - max(top, 0.0))
    r.update(foot_row=foot, top_row=top, apparent_px=px, foot_in_frame=foot <= view.height)
    if max_distance is not None and dist > max_distance:
        r["reasons"].append("too_far")
    if px < (0.15 * view.height if min_px is None else min_px):
        r["reasons"].append("too_small")
    if occluders:
        from shapely.geometry import LineString
        line = LineString([(view.x, view.y), (x, y)])
        if any(line.intersects(o) for o in occluders):
            r["reasons"].append("occluded")
    r["verdict"] = "not_visible" if r["reasons"] else "should_be_visible"
    return r


def _primary(reasons):
    return max(reasons, key=PRIORITY.get)   # the reason farthest from being visible (too_far before too_small)


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _occluders(path):
    from shapely.geometry import shape
    gj = json.load(open(path, encoding="utf-8"))
    return [shape(ft["geometry"]) for ft in gj["features"] if ft.get("geometry")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("views")
    ap.add_argument("targets")
    ap.add_argument("--target-height", type=float, required=True, help="metres, unless the targets have a height")
    ap.add_argument("--camera-height", type=float, default=2.5)
    ap.add_argument("--min-px", type=float, help="default: 15%% of each view's height")
    ap.add_argument("--max-distance", type=float)
    ap.add_argument("--occluders", help="GeoJSON of building footprints, in the same projected CRS")
    ap.add_argument("--detected", help="CSV with an id column: targets the detector matched")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    views = [View(float(v["x"]), float(v["y"]), float(v["azimuth"]), float(v["hfov"]), int(v["width"]),
                  int(v["height"]), a.camera_height, v["view_id"]) for v in _read(a.views)]
    occ = _occluders(a.occluders) if a.occluders else ()
    detected = {r["id"] for r in _read(a.detected)} if a.detected else None
    rows, reasons = [], Counter()
    for t in _read(a.targets):
        h = float(t["height"]) if t.get("height") else a.target_height
        res = [(v.view_id, expect(v, float(t["x"]), float(t["y"]), h, a.min_px, a.max_distance, occ)) for v in views]
        seen = [vid for vid, r in res if r["verdict"] == "should_be_visible"]
        why = ""
        if not seen:
            best = min((r for _, r in res), key=lambda r: PRIORITY[_primary(r["reasons"])])
            why = ";".join(best["reasons"])
            reasons[_primary(best["reasons"])] += 1
        row = {"id": t["id"], "verdict": "should_be_visible" if seen else "not_visible", "views": ";".join(seen),
               "reasons": why}
        if detected is not None:
            row["detected"] = int(t["id"] in detected)
        rows.append(row)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    vis = [r for r in rows if r["verdict"] == "should_be_visible"]
    summary = {"targets": len(rows), "should_be_visible": len(vis), "not_visible_reasons": dict(reasons),
               "views": len(views), "camera_height_m": a.camera_height}
    if detected is not None:
        summary["detected_of_visible"] = sum(r["detected"] for r in vis)
        summary["detected_of_not_visible"] = sum(r["detected"] for r in rows if r["verdict"] != "should_be_visible")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())

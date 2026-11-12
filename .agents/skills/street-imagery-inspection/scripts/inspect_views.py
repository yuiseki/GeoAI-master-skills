"""Inspect 360 street-level pictures for poles: find them with an open-vocabulary detector (OWLv2) in four level
views, measure each pole's lean against the other vertical lines of its view, measure the vegetation around its
top, and place it on the map from the bearing and the depression angle of its foot.

    uvx --with numpy --with scipy --with pillow --with scikit-image --with torch --with transformers \
        python inspect_views.py MANIFEST.csv IMAGES_DIR OUTDIR [--device cuda] [--camera-height 2.5] [--views-dir V]

MANIFEST.csv: id, lon, lat, azimuth, file (the output of panoramax_fetch.py). Writes OUTDIR/poles.csv (one row
per detection: picture, view yaw, box, score, query, bearing, distance, estimated lat/lon, lean, reference, veg
share), OUTDIR/pole_sites.csv (detections merged into sites within --merge-m) and OUTDIR/audit.json.

Estimates, not measurements:
  - Position: the foot's depression angle below the horizon and an assumed camera height give the distance
    (distance = height / tan(angle)). The camera height is not in the metadata; 2.5 m is a guess for a roof rig.
    A foot hidden by a car or out of view gives no position. Flat ground is assumed.
  - Lean: only the component across the line of sight, against the median of other vertical lines (pole_lean.py).
  - Vegetation: share of excess-green pixels (2G - R - B > 20) in a box three times the pole's width around its
    upper 40 %. Green paint and lawns count too; it says where leaves may touch a pole, not that they do.
"""

import argparse
import csv
import json
import math
import os
import sys

import numpy as np

QUERIES = ["a utility pole", "a street light pole", "a telegraph pole"]
YAWS = (0, 90, 180, 270)
FOV = 90
VIEW = (1024, 1024)
R = 6371008.8


def pole_like(box, view_h, min_aspect=3.0, min_height=0.15):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    return w > 0 and h / w >= min_aspect and h >= min_height * view_h


def nms(boxes, scores, iou=0.5):
    order = list(np.argsort(scores)[::-1])
    keep = []
    while order:
        i = order.pop(0)
        keep.append(int(i))
        rest = []
        for j in order:
            a, b = boxes[i], boxes[j]
            ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
            iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
            inter = ix * iy
            union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
            if union <= 0 or inter / union < iou:
                rest.append(j)
        order = rest
    return sorted(keep)


def exg_mask(img, threshold=20):
    a = np.asarray(img, np.int32)
    return (2 * a[..., 1] - a[..., 0] - a[..., 2]) > threshold


def vegetation_share(img, box, widen=3.0, top_part=0.4):
    x0, y0, x1, y1 = box
    h, w = np.asarray(img).shape[:2]
    cx, bw = (x0 + x1) / 2, (x1 - x0) * widen
    bx0, bx1 = int(max(0, cx - bw / 2)), int(min(w, cx + bw / 2))
    by0, by1 = int(max(0, y0)), int(min(h, y0 + (y1 - y0) * top_part))
    if bx1 <= bx0 or by1 <= by0:
        return 0.0
    m = exg_mask(np.asarray(img)[by0:by1, bx0:bx1])
    return float(m.mean())


def foot_distance(y_foot, view_h, view_w, fov, camera_height):
    """Horizontal distance (m) to a point on flat ground seen y_foot pixels down a level view."""
    f = (view_w / 2) / math.tan(math.radians(fov) / 2)
    dy = y_foot - (view_h - 1) / 2
    if dy <= 0:
        return None
    return camera_height / (dy / f)


def destination(lat, lon, bearing, dist):
    d, t = dist / R, math.radians(bearing)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(t))
    l2 = l1 + math.atan2(math.sin(t) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def merge_points(pts, radius_m=5.0):
    """Labels joining points closer than radius_m (single linkage)."""
    from scipy.cluster.hierarchy import fcluster, linkage
    if len(pts) < 2:
        return list(range(len(pts)))
    lat0 = np.mean([p[0] for p in pts])
    xy = np.array([[math.radians(p[1]) * R * math.cos(math.radians(lat0)), math.radians(p[0]) * R] for p in pts])
    return [int(v) for v in fcluster(linkage(xy, "single"), radius_m, "distance")]


class Detector:
    def __init__(self, device="cpu", name="google/owlv2-base-patch16-ensemble"):
        import torch
        from transformers import Owlv2ForObjectDetection, Owlv2Processor
        self.torch, self.device, self.name = torch, device, name
        self.proc = Owlv2Processor.from_pretrained(name)
        self.model = Owlv2ForObjectDetection.from_pretrained(name).to(device).eval()

    def __call__(self, img, queries=QUERIES, threshold=0.15):
        torch = self.torch
        inputs = self.proc(text=[queries], images=img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model(**inputs)
        side = max(img.size)                      # OWLv2 pads to a square: boxes are in the padded frame
        res = self.proc.image_processor.post_process_object_detection(out, threshold=threshold,
                                                      target_sizes=torch.tensor([[side, side]]).to(self.device))[0]
        return [(tuple(float(v) for v in b), float(s), queries[int(l)])
                for b, s, l in zip(res["boxes"].cpu(), res["scores"].cpu(), res["labels"].cpu())]


def main(argv=None):
    from PIL import Image
    from equirect_view import heading_of_column, perspective
    from pole_lean import pole_lean
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("manifest")
    a.add_argument("images")
    a.add_argument("outdir")
    a.add_argument("--device", default="cpu")
    a.add_argument("--camera-height", type=float, default=2.5)
    a.add_argument("--merge-m", type=float, default=4.0)
    a.add_argument("--views-dir", help="also save each view (JPEG) here")
    a.add_argument("--threshold", type=float, default=0.15)
    a = a.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    det = Detector(a.device)
    rows, audit = [], {"pictures": 0, "views": 0, "detections": 0, "pole_like": 0, "with_position": 0}
    for m in csv.DictReader(open(a.manifest, encoding="utf-8")):
        pano = np.asarray(Image.open(os.path.join(a.images, os.path.basename(m["file"]))).convert("RGB"))
        audit["pictures"] += 1
        for yaw in YAWS:
            view = perspective(pano, yaw, 0.0, FOV, VIEW)
            img = Image.fromarray(view)
            if a.views_dir:
                os.makedirs(a.views_dir, exist_ok=True)
                img.save(os.path.join(a.views_dir, f"{m['id']}_y{yaw}.jpg"), quality=90)
            audit["views"] += 1
            found = det(img, threshold=a.threshold)
            audit["detections"] += len(found)
            cand = [(b, s, q) for b, s, q in found if pole_like(b, VIEW[1])]
            keep = nms([c[0] for c in cand], [c[1] for c in cand])
            gray = view.mean(axis=2) / 255.0
            for k in keep:
                b, s, q = cand[k]
                audit["pole_like"] += 1
                lean = pole_lean(gray, b)
                bearing = heading_of_column(float(m["azimuth"] or 0), yaw, (b[0] + b[2]) / 2, VIEW[0], FOV)
                dist = foot_distance(b[3], VIEW[1], VIEW[0], FOV, a.camera_height) if b[3] < VIEW[1] - 2 else None
                plat = plon = None
                if dist is not None and dist < 60:
                    plat, plon = destination(float(m["lat"]), float(m["lon"]), bearing, dist)
                    audit["with_position"] += 1
                rows.append({"picture": m["id"], "yaw": yaw, "x0": round(b[0], 1), "y0": round(b[1], 1),
                             "x1": round(b[2], 1), "y1": round(b[3], 1), "score": round(s, 3), "query": q,
                             "bearing": round(bearing, 1), "distance_m": None if dist is None else round(dist, 1),
                             "lat": plat, "lon": plon, "lean_deg": lean["lean_deg"], "raw_deg": lean["raw_deg"],
                             "reference_deg": lean["reference_deg"], "corrected": lean["corrected"],
                             "pole_lines": lean["pole_lines"], "reference_lines": lean["reference_lines"],
                             "veg_share": round(vegetation_share(view, b), 4)})
    cols = ["picture", "yaw", "x0", "y0", "x1", "y1", "score", "query", "bearing", "distance_m", "lat", "lon",
            "lean_deg", "raw_deg", "reference_deg", "corrected", "pole_lines", "reference_lines", "veg_share"]
    placed = [r for r in rows if r["lat"] is not None]
    labels = merge_points([(r["lat"], r["lon"]) for r in placed], a.merge_m)
    for r, l in zip(placed, labels):
        r["site"] = l
    with open(os.path.join(a.outdir, "poles.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["site"])
        w.writeheader()
        w.writerows(rows)
    sites = {}
    for r in placed:
        sites.setdefault(r["site"], []).append(r)
    with open(os.path.join(a.outdir, "pole_sites.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["site", "sightings", "pictures", "lat", "lon", "median_abs_lean_deg", "max_abs_lean_deg",
                    "max_veg_share"])
        for k, g in sorted(sites.items()):
            leans = [abs(r["lean_deg"]) for r in g if r["lean_deg"] is not None and r["corrected"]]
            w.writerow([k, len(g), len({r["picture"] for r in g}), np.mean([r["lat"] for r in g]),
                        np.mean([r["lon"] for r in g]), np.median(leans) if leans else "",
                        max(leans) if leans else "", max(r["veg_share"] for r in g)])
    audit.update(sites=len(sites), camera_height_m=a.camera_height, merge_m=a.merge_m, model=det.name,
                 queries=QUERIES, threshold=a.threshold, yaws=list(YAWS), fov=FOV)
    with open(os.path.join(a.outdir, "audit.json"), "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=1)
    print(json.dumps(audit))


if __name__ == "__main__":
    sys.exit(main())

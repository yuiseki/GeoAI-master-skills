"""Street-level inspection of a Bordeaux suburb from open 360 pictures (Panoramax, Bordeaux Métropole, October
2025): the Street View Insights examples "inspect leaning utility poles or grade road surface condition", with road
surface material and vegetation near poles, placed on the map and counted per H3 cell.

    CUDA_VISIBLE_DEVICES=0 uvx --python 3.12 --with numpy --with scipy --with pandas --with pillow --with scikit-image \
        --with scikit-learn --with torch --with torchvision --with open_clip_torch --with transformers --with h3 \
        --with matplotlib python scripts/run.py STEP

Steps: fetch, roadviews, poles, damage, material, osm, osmpoles, aggregate, review_sample, maps (or all).
The pictures are fetched with the skill's panoramax_fetch.py; large files go to
artifacts/_playground/bordeaux-street-imagery/, the tables the report cites to outputs/.
"""

import csv
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[2]
ART = ROOT / "artifacts" / "_playground" / "bordeaux-street-imagery"
OUT = HERE / "outputs"
SKILL = ROOT / ".agents" / "skills" / "street-imagery-inspection" / "scripts"
PX = ART / "panoramax"
BBOX = (-0.72, 44.84, -0.68, 44.87)
SEED = 20261112
DEVICE = "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu"
# The forward road view: level enough to see the road ahead, below it the roof rack of the vehicle.
ROAD = {"yaw": 0.0, "pitch": -15.0, "fov": 70.0, "size": (1024, 768), "crop": (0.2, 0.36, 0.8, 0.64)}
OVERPASS = "https://overpass.yuiseki.net/api/interpreter"


def sh(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def manifest():
    return list(csv.DictReader(open(PX / "manifest.csv", encoding="utf-8")))


def fetch():
    sh(sys.executable, SKILL / "panoramax_fetch.py", PX, "--bbox", *BBOX, "--n", 300, "--seed", SEED,
       "--producer", "bordeaux métropole", "--fov", 360, "--since", "2025-09-01", "--asset", "hd")
    (OUT / "fetch_audit.json").write_bytes((PX / "audit.json").read_bytes())


def roadviews():
    """The road band of the forward view of every picture."""
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(SKILL))
    from equirect_view import perspective
    d = ART / "views_road"
    d.mkdir(exist_ok=True)
    for m in manifest():
        pano = np.asarray(Image.open(PX / m["file"]).convert("RGB"))
        v = Image.fromarray(perspective(pano, ROAD["yaw"], ROAD["pitch"], ROAD["fov"], ROAD["size"]))
        w, h = v.size
        x0, y0, x1, y1 = ROAD["crop"]
        v.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))).save(d / f"{m['id']}.jpg", quality=92)


def poles():
    sh(sys.executable, SKILL / "inspect_views.py", PX / "manifest.csv", PX / "images", ART / "poles",
       "--device", DEVICE, "--views-dir", ART / "views_level")
    for f in ("audit.json",):
        (OUT / f"poles_{f}").write_bytes((ART / "poles" / f).read_bytes())


def damage():
    probe = ART / "damage_probe" / "probe.npz"
    sh(sys.executable, SKILL / "surface_damage.py", "predict", probe, ART / "views_road", ART / "damage_patches.csv",
       "--device", DEVICE, "--top", 0.0, "--bottom", 1.0, "--patch", 200)
    for f in ("train.json", "eval_united_states.json"):
        (OUT / f"damage_{f}").write_bytes((ART / "damage_probe" / f).read_bytes())


def material():
    sh(sys.executable, SKILL / "surface_material.py", ART / "views_road", ART / "material.csv", "--device", DEVICE,
       "--top", 0.0, "--bottom", 1.0, "--left", 0.0, "--right", 1.0)


def osm():
    """OSM ways with a surface tag in the box (our own Overpass, data of 2025-09-14), the nearest car road to each
    picture within 12 m, and the agreement of the zero-shot material with its surface."""
    import urllib.parse
    import urllib.request
    sys.path.insert(0, str(SKILL))
    from surface_material import agreement, osm_class
    f = ART / "osm_surface.json"
    if not f.exists():
        s, w, n, e = BBOX[1] - 0.01, BBOX[0] - 0.01, BBOX[3] + 0.01, BBOX[2] + 0.01
        q = f'[out:json][timeout:500];way["highway"]({s},{w},{n},{e});out geom tags;'
        req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "GeoAI-master-skills"})
        with urllib.request.urlopen(req, timeout=900) as r:
            f.write_bytes(r.read())
    data = json.loads(f.read_text(encoding="utf-8"))
    car = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service",
           "living_street", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "track"}
    ways = [w for w in data["elements"] if w.get("tags", {}).get("highway") in car and "geometry" in w]
    R = 6371008.8

    def dist(lat, lon, a, b):
        k = math.cos(math.radians(lat))
        px, py = math.radians(lon) * R * k, math.radians(lat) * R
        ax, ay = math.radians(a["lon"]) * R * k, math.radians(a["lat"]) * R
        bx, by = math.radians(b["lon"]) * R * k, math.radians(b["lat"]) * R
        dx, dy = bx - ax, by - ay
        t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)

    mat = {r["view"][:-4]: r["surface"] for r in csv.DictReader(open(ART / "material.csv", encoding="utf-8"))}
    rows = []
    for m in manifest():
        lat, lon = float(m["lat"]), float(m["lon"])
        best = (1e9, None)
        for w in ways:
            g = w["geometry"]
            for a, b in zip(g, g[1:]):
                d = dist(lat, lon, a, b)
                if d < best[0]:
                    best = (d, w)
        w = best[1]
        tag = w["tags"].get("surface") if w is not None and best[0] <= 12 else None
        rows.append({"id": m["id"], "nearest_m": round(best[0], 1), "highway": w["tags"].get("highway") if w else None,
                     "osm_surface": tag, "osm_class": osm_class(tag), "predicted": mat.get(m["id"])})
    with open(ART / "material_vs_osm.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    t = agreement([r["predicted"] for r in rows], [r["osm_class"] for r in rows])
    ref = [r["osm_class"] for r in rows if r["osm_class"]]
    major = max(set(ref), key=ref.count) if ref else None
    t["majority_class"] = major
    t["majority_accuracy"] = ref.count(major) / len(ref) if ref else None
    t["pictures"] = len(rows)
    t["no_road_within_12m"] = sum(r["nearest_m"] > 12 for r in rows)
    t["road_without_surface_tag"] = sum(r["nearest_m"] <= 12 and r["osm_surface"] is None for r in rows)
    t["osm_base"] = data.get("osm3s", {}).get("timestamp_osm_base")
    pred = {}
    for r in rows:
        pred[r["predicted"]] = pred.get(r["predicted"], 0) + 1
    t["predicted_counts"] = pred
    json.dump(t, open(OUT / "material_vs_osm.json", "w", encoding="utf-8"), indent=1)
    print(t)


def osmpoles():
    """Estimated pole sites against the poles and street lamps mapped in OSM (our own Overpass, 2025-09-14 data).
    OSM maps only some of them, so this measures how far an estimate is from a mapped one where one is near; it
    does not count the poles found."""
    import urllib.parse
    import urllib.request
    import numpy as np
    from scipy.spatial import cKDTree
    f = ART / "osm_poles.json"
    if not f.exists():
        s, w, n, e = BBOX[1] - 0.005, BBOX[0] - 0.005, BBOX[3] + 0.005, BBOX[2] + 0.005
        q = (f'[out:json][timeout:500];(node["power"="pole"]({s},{w},{n},{e});'
             f'node["highway"="street_lamp"]({s},{w},{n},{e});node["power"="tower"]({s},{w},{n},{e}););out;')
        req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "GeoAI-master-skills"})
        with urllib.request.urlopen(req, timeout=900) as r:
            f.write_bytes(r.read())
    data = json.loads(f.read_text(encoding="utf-8"))
    nodes = [(el["lat"], el["lon"], el["tags"].get("power") or el["tags"].get("highway")) for el in data["elements"]]
    sites = list(csv.DictReader(open(ART / "poles" / "pole_sites.csv", encoding="utf-8")))
    R, lat0 = 6371008.8, 44.855
    xy = lambda la, lo: (math.radians(lo) * R * math.cos(math.radians(lat0)), math.radians(la) * R)
    tree = cKDTree([xy(a, b) for a, b, _ in nodes])
    d, _ = tree.query([xy(float(s["lat"]), float(s["lon"])) for s in sites], k=1)
    kinds = {}
    for _, _, k in nodes:
        kinds[k] = kinds.get(k, 0) + 1
    out = {"osm_base": data.get("osm3s", {}).get("timestamp_osm_base"), "osm_nodes": kinds, "sites": len(sites),
           "median_m_to_nearest_osm": float(np.median(d)), "share_within_5m": float(np.mean(d <= 5)),
           "share_within_10m": float(np.mean(d <= 10)), "share_beyond_25m": float(np.mean(d > 25))}
    json.dump(out, open(OUT / "poles_vs_osm.json", "w", encoding="utf-8"), indent=1)
    print(out)


def aggregate():
    """Per picture and per H3 cell (resolution 9): damage share, material, poles, leans, vegetation."""
    import h3
    import numpy as np
    pics = {m["id"]: m for m in manifest()}
    dmg = {}
    for r in csv.DictReader(open(ART / "damage_patches.csv", encoding="utf-8")):
        dmg.setdefault(r["view"][:-4], []).append(float(r["p_damage"]))
    mat = {r["view"][:-4]: r["surface"] for r in csv.DictReader(open(ART / "material.csv", encoding="utf-8"))}
    poles = list(csv.DictReader(open(ART / "poles" / "poles.csv", encoding="utf-8")))
    per = []
    for pid, m in pics.items():
        p = dmg.get(pid, [])
        mine = [r for r in poles if r["picture"] == pid]
        leans = [abs(float(r["lean_deg"])) for r in mine if r["lean_deg"] not in ("", "None") and r["corrected"] == "True"]
        per.append({"id": pid, "lat": float(m["lat"]), "lon": float(m["lon"]), "h3_r9": h3.latlng_to_cell(float(m["lat"]), float(m["lon"]), 9),
                    "patches": len(p), "damaged_share": float(np.mean([v >= 0.5 for v in p])) if p else None,
                    "mean_p_damage": float(np.mean(p)) if p else None, "material": mat.get(pid),
                    "poles": len(mine), "max_abs_lean_deg": max(leans) if leans else None,
                    "max_veg_share": max((float(r["veg_share"]) for r in mine), default=None)})
    with open(OUT / "pictures.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per[0].keys()))
        w.writeheader()
        w.writerows(per)
    cells = {}
    for r in per:
        cells.setdefault(r["h3_r9"], []).append(r)
    with open(OUT / "cells_h3r9.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["h3_r9", "pictures", "mean_damaged_share", "poles", "poles_lean_over_5deg", "pictures_veg_over_0.3"])
        for c, g in sorted(cells.items()):
            ds = [r["damaged_share"] for r in g if r["damaged_share"] is not None]
            w.writerow([c, len(g), f"{np.mean(ds):.3f}" if ds else "", sum(r["poles"] for r in g),
                        sum(1 for r in g if r["max_abs_lean_deg"] is not None and r["max_abs_lean_deg"] > 5),
                        sum(1 for r in g if r["max_veg_share"] is not None and r["max_veg_share"] > 0.3)])
    leans = [abs(float(r["lean_deg"])) for r in poles if r["lean_deg"] not in ("", "None") and r["corrected"] == "True"]
    ds = [r["damaged_share"] for r in per if r["damaged_share"] is not None]
    summ = {"pictures": len(per), "cells": len(cells), "pole_detections": len(poles),
            "pole_detections_corrected": len(leans),
            "pole_detections_uncorrected": sum(1 for r in poles if r["corrected"] != "True"),
            "median_abs_lean_deg": float(np.median(leans)) if leans else None,
            "detections_lean_over_5deg": sum(v > 5 for v in leans),
            "detections_veg_over_0.3": sum(float(r["veg_share"]) > 0.3 for r in poles),
            "mean_damaged_share": float(np.mean(ds)) if ds else None,
            "pictures_damaged_share_over_0.5": sum(v > 0.5 for v in ds)}
    json.dump(summ, open(OUT / "summary.json", "w", encoding="utf-8"), indent=1)
    print(summ)


def review_sample():
    """Uniform random samples for a visual check: 40 road crops and 40 pole detections, as contact sheets with
    numbers. The labels go in outputs/review_*.csv, written by whoever looks (and saying who)."""
    from PIL import Image, ImageDraw
    rng = random.Random(SEED)
    roads = sorted((ART / "views_road").glob("*.jpg"))
    pick = rng.sample(roads, min(40, len(roads)))
    dmg = {}
    for r in csv.DictReader(open(ART / "damage_patches.csv", encoding="utf-8")):
        dmg.setdefault(r["view"], []).append(r)
    sheet = Image.new("RGB", (4 * 614, 10 * 215), "white")
    rows = []
    for i, f in enumerate(pick):
        im = Image.open(f).convert("RGB")
        dr = ImageDraw.Draw(im)
        for r in dmg.get(f.name, []):
            col = "red" if float(r["p_damage"]) >= 0.5 else "lime"
            dr.rectangle([int(r["x0"]), int(r["y0"]), int(r["x1"]) - 1, int(r["y1"]) - 1], outline=col, width=3)
            dr.text((int(r["x0"]) + 4, int(r["y0"]) + 4), r["p_damage"], fill=col)
        dr.text((6, 6), str(i + 1), fill="yellow")
        sheet.paste(im.resize((614, 215)), ((i % 4) * 614, (i // 4) * 215))
        for r in dmg.get(f.name, []):
            rows.append({"n": i + 1, "view": f.name, "x0": r["x0"], "p_damage": r["p_damage"], "visual_damage": ""})
    sheet.save(ART / "review_road_sheet.jpg", quality=85)
    with open(ART / "review_road_template.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    poles = list(csv.DictReader(open(ART / "poles" / "poles.csv", encoding="utf-8")))
    pp = rng.sample(poles, min(40, len(poles)))
    sheet = Image.new("RGB", (8 * 300, 5 * 420), "white")
    for i, r in enumerate(pp):
        im = Image.open(ART / "views_level" / f"{r['picture']}_y{r['yaw']}.jpg").convert("RGB")
        x0, y0, x1, y1 = (float(r[k]) for k in ("x0", "y0", "x1", "y1"))
        cx, h = (x0 + x1) / 2, (y1 - y0)
        crop = im.crop((int(cx - 0.35 * h), int(y0 - 0.05 * h), int(cx + 0.35 * h), int(y1 + 0.05 * h))).resize((300, 420))
        d = ImageDraw.Draw(crop)
        d.text((4, 4), f"{i + 1} lean {r['lean_deg'][:5]} veg {r['veg_share'][:4]}", fill="yellow")
        sheet.paste(crop, ((i % 8) * 300, (i // 8) * 420))
        r["n"] = i + 1
    sheet.save(ART / "review_pole_sheet.jpg", quality=85)
    with open(ART / "review_pole_template.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["n", "picture", "yaw", "score", "lean_deg", "corrected", "veg_share", "is_pole", "visibly_leaning",
                    "leaves_touch"])
        for r in pp:
            w.writerow([r["n"], r["picture"], r["yaw"], r["score"], r["lean_deg"], r["corrected"], r["veg_share"],
                        "", "", ""])


def maps():
    import h3
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    per = list(csv.DictReader(open(OUT / "pictures.csv", encoding="utf-8")))
    cells = list(csv.DictReader(open(OUT / "cells_h3r9.csv", encoding="utf-8")))
    sites = list(csv.DictReader(open(ART / "poles" / "pole_sites.csv", encoding="utf-8")))
    fig, axes = plt.subplots(1, 2, figsize=(15, 7), dpi=120)
    cmap = plt.get_cmap("YlOrRd")
    for c in cells:
        if c["mean_damaged_share"]:
            b = [(lng, lat) for lat, lng in h3.cell_to_boundary(c["h3_r9"])]
            axes[0].add_patch(Polygon(b, fc=cmap(float(c["mean_damaged_share"])), ec="#999", lw=0.3))
    axes[0].scatter([float(r["lon"]) for r in per], [float(r["lat"]) for r in per], s=3, c="k")
    axes[0].set_title("Road damage indicator: share of road patches with p >= 0.5, per H3 r9 cell")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
    fig.colorbar(sm, ax=axes[0], shrink=0.7)
    lean = [(float(s["lon"]), float(s["lat"]), float(s["max_abs_lean_deg"]) if s["max_abs_lean_deg"] else -1,
             float(s["max_veg_share"])) for s in sites]
    axes[1].scatter([p[0] for p in lean], [p[1] for p in lean], s=8,
                    c=["#999" if p[2] < 0 else ("#d7301f" if p[2] > 5 else "#2c7fb8") for p in lean])
    axes[1].scatter([p[0] for p in lean if p[3] > 0.3], [p[1] for p in lean if p[3] > 0.3], s=40, facecolors="none",
                    edgecolors="green")
    axes[1].set_title("Pole sites (estimated): red lean > 5 deg, grey not corrected; green ring vegetation > 0.3")
    for ax in axes:
        ax.set_xlim(BBOX[0], BBOX[2])
        ax.set_ylim(BBOX[1], BBOX[3])
        ax.set_aspect(1 / math.cos(math.radians(44.855)))
    fig.suptitle("Mérignac (Bordeaux Métropole), Panoramax 360 pictures of 2025-10, uniform sample")
    fig.savefig(OUT / "maps.png", bbox_inches="tight")


STEPS = {"fetch": fetch, "roadviews": roadviews, "poles": poles, "damage": damage, "material": material,
         "osm": osm, "osmpoles": osmpoles, "aggregate": aggregate, "review_sample": review_sample, "maps": maps}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    for s in (STEPS if sys.argv[1] == "all" else sys.argv[1:]):
        STEPS[s]()

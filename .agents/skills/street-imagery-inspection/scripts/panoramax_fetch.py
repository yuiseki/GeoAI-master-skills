"""List the street-level pictures of Panoramax in a box, draw a uniform random sample, and download it with a manifest.

    uvx python panoramax_fetch.py OUTDIR --bbox W S E N --n 200 [--seed 0] [--producer NAME] [--fov 360] \
        [--since 2025-01-01] [--asset sd|hd] [--api https://api.panoramax.xyz/api]

Panoramax (https://panoramax.fr) is an open, federated street-level imagery commons; its search API needs no key.
Pictures carry their own licence (etalab-2.0 or CC-BY-SA-4.0 seen in France); the manifest keeps it per picture.

The box is searched tile by tile; a tile that returns the page limit is split in four until none does, so every
picture of the box is listed once. Filters (producer, field of view, date) are counted; the sample is drawn
uniformly without replacement from the eligible pictures with the seed. Pictures are dense where the capture
vehicle drove slowly or often, so a uniform sample of pictures is a sample of capture effort, not of road length.

Writes OUTDIR/manifest.csv (id, collection, lon, lat, datetime, azimuth, producer, camera, fov, licence,
annotations, file, sha256, sd, hd), OUTDIR/images/<id>.jpg and OUTDIR/audit.json.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

API = "https://api.panoramax.xyz/api"


def http_json(url, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GeoAI-master-skills"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def api_search(api, since=None):
    """since: also passed to the API as a STAC datetime interval, so the server sends fewer pictures."""
    def search(bbox, limit):
        q = {"bbox": ",".join(f"{v:.7f}" for v in bbox), "limit": limit}
        if since:
            q["datetime"] = f"{since}T00:00:00Z/.."
        got = http_json(f"{api}/search?{urllib.parse.urlencode(q)}").get("features", [])
        print(f"tile {bbox} -> {len(got)}", file=sys.stderr, flush=True)
        return got
    return search


def list_pictures(bbox, search, limit=1000, tile=0.01):
    """Every picture in the box: tiles of `tile` degrees, split in four while a tile returns `limit`."""
    w, s, e, n = bbox
    todo, seen = [], {}
    x = w
    while x < e:
        y = s
        while y < n:
            todo.append((x, y, min(x + tile, e), min(y + tile, n)))
            y += tile
        x += tile
    while todo:
        b = todo.pop()
        got = search(b, limit)
        if len(got) >= limit and (b[2] - b[0]) > 1e-5:
            mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            todo += [(b[0], b[1], mx, my), (mx, b[1], b[2], my), (b[0], my, mx, b[3]), (mx, my, b[2], b[3])]
            continue
        for f in got:
            lon, lat = f["geometry"]["coordinates"]
            if w <= lon <= e and s <= lat <= n:
                seen[f["id"]] = f
    return list(seen.values())


def feature_row(f):
    p = f["properties"]
    io = p.get("pers:interior_orientation") or {}
    a = f.get("assets", {})
    return {"id": f["id"], "collection": f.get("collection"), "lon": f["geometry"]["coordinates"][0],
            "lat": f["geometry"]["coordinates"][1], "datetime": p.get("datetime"), "azimuth": p.get("view:azimuth"),
            "producer": p.get("geovisio:producer"), "camera": io.get("camera_model"), "fov": io.get("field_of_view"),
            "licence": p.get("license"), "annotations": len(p.get("annotations") or []),
            "sd": a.get("sd", {}).get("href"), "hd": a.get("hd", {}).get("href")}


def _number(v):
    """The field of view as a number: the API gives an int, a CSV read back gives text."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sample(rows, n, seed=0, producer=None, fov=None, since=None):
    audit = {"listed": len(rows), "other_producer": 0, "other_fov": 0, "too_old": 0}
    ok = []
    for r in sorted(rows, key=lambda r: r["id"]):
        if producer and r["producer"] != producer:
            audit["other_producer"] += 1
        elif fov and _number(r["fov"]) != fov:
            audit["other_fov"] += 1
        elif since and (r["datetime"] or "") < since:
            audit["too_old"] += 1
        else:
            ok.append(r)
    audit["eligible"] = len(ok)
    kept = random.Random(seed).sample(ok, min(n, len(ok)))
    audit["sampled"] = len(kept)
    return kept, audit


def download(url, path):
    for k in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GeoAI-master-skills"})
            with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
                f.write(r.read())
            break
        except Exception:
            if k == 4:
                raise
            time.sleep(5 * (k + 1))
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("outdir")
    a.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("W", "S", "E", "N"))
    a.add_argument("--n", type=int, default=200)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--producer")
    a.add_argument("--fov", type=int)
    a.add_argument("--since")
    a.add_argument("--asset", choices=["sd", "hd"], default="sd")
    a.add_argument("--api", default=API)
    a = a.parse_args(argv)
    os.makedirs(os.path.join(a.outdir, "images"), exist_ok=True)
    feats = list_pictures(a.bbox, api_search(a.api, a.since))
    rows = [feature_row(f) for f in feats]
    with open(os.path.join(a.outdir, "listed.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["id"]))
    kept, audit = sample(rows, a.n, a.seed, a.producer, a.fov, a.since)
    for r in kept:
        r["file"] = f"images/{r['id']}.jpg"
        p = os.path.join(a.outdir, r["file"])
        r["sha256"] = download(r[a.asset], p) if not os.path.exists(p) else hashlib.sha256(open(p, "rb").read()).hexdigest()
    with open(os.path.join(a.outdir, "manifest.csv"), "w", newline="", encoding="utf-8") as f:
        cols = ["id", "collection", "lon", "lat", "datetime", "azimuth", "producer", "camera", "fov", "licence",
                "annotations", "file", "sha256", "sd", "hd"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(kept, key=lambda r: r["id"]))
    audit.update(bbox=a.bbox, seed=a.seed, producer=a.producer, fov=a.fov, since=a.since, asset=a.asset, api=a.api)
    with open(os.path.join(a.outdir, "audit.json"), "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=1)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())

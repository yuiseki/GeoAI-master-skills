"""Read every 2024 Sentinel-1 RTC (VV) and Sentinel-2 L2A (B03, B08, SCL; cloud cover < 60 %) scene over each box
onto the box's 10 m grid (EPSG:32653, the grid of build_masks.py), nearest neighbour, and cache one .npz per scene
under artifacts/_tameike/tameike-sar-water-area/scenes/<box>/. Sentinel-2 tiles of the same date are merged.
Writes outputs/<box>_scenes.csv (every item found, used or not, and why).

  env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 \
    -p CPUQuota=400% -- uvx --python 3.12 --with numpy --with rasterio --with pyproj --with scipy --with duckdb \
    --with pyflwdir python scripts/fetch_scenes.py
"""

import csv
import json
import os
import sys
import threading
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from build_masks import ART, BOXES, DST, OUT, grid10

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
ORBIT = {"kagawa": 90, "fukuyama": 90, "awaji": 17}  # fixed in EXPERIMENT_PLAN.md
_tokens = {}
_lock = threading.Lock()
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff",
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", GDAL_HTTP_MULTIPLEX="YES", VSI_CACHE="TRUE",
                GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="2")
WORKERS = 8


def token(collection):
    with _lock:
        return _token(collection)


def _token(collection):
    t = _tokens.get(collection)
    if t is None or time.time() - t[1] > 1800:
        with urllib.request.urlopen(f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}", timeout=60) as r:
            _tokens[collection] = (json.loads(r.read())["token"], time.time())
    return _tokens[collection][0]


def search(collection, box, extra=None):
    body = {"collections": [collection], "bbox": list(box), "datetime": "2024-01-01T00:00:00Z/2024-12-31T23:59:59Z",
            "limit": 500, **(extra or {})}
    req = urllib.request.Request(STAC, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["features"]


def read_onto(href, collection, grid, resampling=Resampling.nearest):
    (h, w), tr = grid
    with rasterio.Env(**GDAL_ENV), rasterio.open(f"{href}?{token(collection)}") as src:
        with WarpedVRT(src, crs=DST, transform=tr, width=w, height=h, resampling=resampling) as vrt:
            return vrt.read(1)


def cached(path):
    """A cache file counts only if it loads (a run stopped while writing leaves a broken file)."""
    if not path.exists():
        return False
    try:
        with np.load(path) as z:
            z.files
        return True
    except Exception:
        path.unlink()
        return False


def save(path, **arrays):
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)


def fetch(key):
    box = BOXES[key]
    (h, w), tr10, _, _ = grid10(box)
    grid = ((h, w), tr10)
    d = ART / "scenes" / key
    d.mkdir(parents=True, exist_ok=True)
    log, tasks = [], []

    for f in sorted(search("sentinel-1-rtc", box), key=lambda f: f["properties"]["datetime"]):
        p = f["properties"]
        row = dict(sensor="S1", id=f["id"], datetime=p["datetime"], orbit=p.get("sat:relative_orbit"), used="", why="")
        if p.get("sat:relative_orbit") != ORBIT[key]:
            row["why"] = "other orbit"
            log.append(row)
            continue
        path = d / f"S1_{p['datetime'][:10]}.npz"
        row["used"] = path.name
        log.append(row)

        def s1_task(f=f, path=path, p=p):
            vv = read_onto(f["assets"]["vv"]["href"], "sentinel-1-rtc", grid).astype("float32")
            save(path, vv=vv, id=f["id"], datetime=p["datetime"])
        if not cached(path):
            tasks.append((path.name, s1_task))

    by_date = defaultdict(list)
    for f in search("sentinel-2-l2a", box, {"query": {"eo:cloud_cover": {"lt": 60}}}):
        by_date[f["properties"]["datetime"][:10]].append(f)
    for date in sorted(by_date):
        path = d / f"S2_{date}.npz"
        items = by_date[date]
        for f in items:
            log.append(dict(sensor="S2", id=f["id"], datetime=f["properties"]["datetime"],
                            orbit=f["properties"].get("sat:relative_orbit"), used=path.name, why=""))

        def s2_task(items=items, path=path, date=date):
            b03 = np.zeros((h, w), "uint16")
            b08 = np.zeros((h, w), "uint16")
            scl = np.zeros((h, w), "uint8")
            baseline = set()
            for f in items:
                a = f["assets"]
                g = read_onto(a["B03"]["href"], "sentinel-2-l2a", grid)
                n = read_onto(a["B08"]["href"], "sentinel-2-l2a", grid)
                sc = read_onto(a["SCL"]["href"], "sentinel-2-l2a", grid)
                fill = (b03 == 0) & (g > 0)
                b03[fill], b08[fill], scl[fill] = g[fill], n[fill], sc[fill]
                baseline.add(f["properties"].get("s2:processing_baseline"))
            if len(baseline) != 1:
                raise SystemExit(f"{key} {date}: tiles with different processing baselines {baseline}")
            save(path, b03=b03, b08=b08, scl=scl, baseline=baseline.pop(),
                 ids=json.dumps([f["id"] for f in items]), datetime=items[0]["properties"]["datetime"])
        if not cached(path):
            tasks.append((path.name, s2_task))

    print(key, "to fetch", len(tasks), flush=True)
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(t): name for name, t in tasks}
        for fu in futs:
            fu.result()
            print(key, futs[fu], flush=True)

    with open(OUT / f"{key}_scenes.csv", "w", newline="", encoding="utf-8") as fp:
        wr = csv.DictWriter(fp, fieldnames=list(log[0]))
        wr.writeheader()
        wr.writerows(log)


if __name__ == "__main__":
    for k in sys.argv[1:] or list(BOXES):
        fetch(k)

"""Fetch the Mapterhorn z16 tiles within 220 m of every underpass (exploratory DEM, added after the results).
Three requests at a time, each worker pausing 0.1 s.

uvx --from 'duckdb>=1.5.5' --with numpy python -u scripts/08_mapterhorn.py [--limit N]

Tiles go to artifacts/_flood/underpass-ponding-exposure/dem/mt/16/<x>_<y>.webp; a 404 is kept as an empty .404.
The tile entry (tiles.mapterhorn.com) is overwritten when Mapterhorn updates, so the version file of the day
(download_urls.json) is saved next to the tiles and the log records it. Tiles already saved are skipped.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from dem import tiles_around

HERE = Path(__file__).resolve().parent
ART = HERE.parents[3] / "artifacts/_flood/underpass-ponding-exposure"
URL = "https://tiles.mapterhorn.com/16/{x}/{y}.webp"
UA = {"User-Agent": "yuiseki-geoai-research (GeoAI-master-skills underpass study)"}
RADIUS = 220
PAUSE = 0.1
WORKERS = 3  # concurrent requests to the tile CDN


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return 200, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            err = e
        except (urllib.error.URLError, TimeoutError) as e:
            err = e
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    d = ART / "dem/mt/16"
    d.mkdir(parents=True, exist_ok=True)
    status, body = get("https://download.mapterhorn.com/download_urls.json")
    (ART / "dem/mt/download_urls.json").write_bytes(body)
    version = json.loads(body)["version"]
    pts = duckdb.sql(f"select lon, lat from '{ART / 'raw/underpass.parquet'}'").fetchall()
    need = sorted(set().union(*(tiles_around(lon, lat, 16, RADIUS, 512) for lon, lat in pts)))
    if a.limit:
        need = need[:a.limit]
    got = {200: 0, 404: 0, "skipped": 0}
    started = datetime.now(timezone.utc).isoformat()
    todo = [(x, y) for x, y in need if not (d / f"{x}_{y}.webp").exists() and not (d / f"{x}_{y}.404").exists()]
    got["skipped"] = len(need) - len(todo)

    def one(xy):
        x, y = xy
        status, body = get(URL.format(x=x, y=y))
        (d / f"{x}_{y}.{'webp' if status == 200 else '404'}").write_bytes(body)
        time.sleep(PAUSE)
        return status

    with ThreadPoolExecutor(WORKERS) as pool:
        for i, status in enumerate(pool.map(one, todo)):
            got[status] += 1
            if i % 1000 == 0:
                print(i, len(todo), got, flush=True)
    log = {"started": started, "finished": datetime.now(timezone.utc).isoformat(), "mapterhorn_version": version,
           "zoom": 16, "radius_m": RADIUS, "tiles_needed": len(need), **{str(k): v for k, v in got.items()}}
    print(log, flush=True)
    if not a.limit:
        (ART / "dem/mt/fetch_log.json").write_text(json.dumps(log, indent=1) + "\n")


if __name__ == "__main__":
    main()

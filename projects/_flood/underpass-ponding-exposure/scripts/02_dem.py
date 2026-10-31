"""Fetch the GSI elevation tiles around every underpass (DEM5A z15 and DEM10B z14), one request at a time.

uvx --from 'duckdb>=1.5.5' --with numpy python scripts/02_dem.py [--limit N]

Tiles within 320 m of a point are saved under artifacts/_flood/underpass-ponding-exposure/dem/<layer>/<z>/<x>_<y>.txt.
A 404 (no land) is saved as an empty <x>_<y>.404. Tiles already saved are skipped, so the script can be run again.
Any other HTTP status is retried three times and then stops the run. The log of the run is dem/fetch_log.json.
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from dem import LAYERS, tiles_around

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/underpass-ponding-exposure"
URL = "https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{x}/{y}.txt"
RADIUS = 320
PAUSE = 0.3


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
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
    pts = duckdb.sql(f"select lon, lat from '{ART / 'raw/underpass.parquet'}'").fetchall()
    log = {"started": datetime.now(timezone.utc).isoformat(), "radius_m": RADIUS, "layers": {}}
    for layer, z in LAYERS.items():
        need = sorted(set().union(*(tiles_around(lon, lat, z, RADIUS) for lon, lat in pts)))
        if a.limit:
            need = need[:a.limit]
        d = ART / "dem" / layer / str(z)
        d.mkdir(parents=True, exist_ok=True)
        got = {200: 0, 404: 0, "skipped": 0}
        for i, (x, y) in enumerate(need):
            if (d / f"{x}_{y}.txt").exists() or (d / f"{x}_{y}.404").exists():
                got["skipped"] += 1
                continue
            status, body = get(URL.format(layer=layer, z=z, x=x, y=y))
            if status == 200:
                (d / f"{x}_{y}.txt").write_bytes(body)
            else:
                (d / f"{x}_{y}.404").write_bytes(b"")
            got[status] += 1
            if i % 500 == 0:
                print(layer, i, len(need), got, flush=True)
            time.sleep(PAUSE)
        log["layers"][layer] = {"zoom": z, "tiles_needed": len(need), **{str(k): v for k, v in got.items()}}
        print(layer, log["layers"][layer], flush=True)
    log["finished"] = datetime.now(timezone.utc).isoformat()
    if not a.limit:
        (ART / "dem/fetch_log.json").write_text(json.dumps(log, indent=1) + "\n")


if __name__ == "__main__":
    main()

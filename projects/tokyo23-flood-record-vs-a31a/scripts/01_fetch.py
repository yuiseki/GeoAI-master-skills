"""Fetch the inputs at pinned revisions into artifacts/tokyo23-flood-record-vs-a31a/raw/.

uv run --with 'duckdb>=1.5.5' python scripts/01_fetch.py
"""
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

import duckdb

ART = Path(__file__).resolve().parents[3] / "artifacts" / "tokyo23-flood-record-vs-a31a" / "raw"
ART.mkdir(parents=True, exist_ok=True)

SRC = {
    "wards": ("hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet",
              "select code5, name, population, geometry from src where code5 between '13101' and '13123'"),
    "flood_record_area": ("hf://datasets/yuiseki/tokyo-flood-record-jp@354b0d9f8030347192eaa387500f60da76c07e1a/parquet/flood_area.parquet", None),
    "flood_record_point": ("hf://datasets/yuiseki/tokyo-flood-record-jp@354b0d9f8030347192eaa387500f60da76c07e1a/parquet/flood_point.parquet", None),
    "a31a": ("hf://datasets/yuiseki/ksj-a31a-flood-tokyo23@5b2259273128d0b79b491eb758abe0db67c4feac/parquet/flood_area.parquet", None),
    "rain_daily": ("hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet/daily.parquet", None),
    "rain_hourly": ("hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet/hourly.parquet", None),
    "rain_stations": ("hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet/stations.parquet", None),
    "osm_waterway": ("hf://datasets/yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664/parquet/planet_osm_line.parquet",
                     "select osm_id, waterway, name, tunnel, way from src where waterway is not null"),
    "worldcover": ("https://huggingface.co/datasets/yuiseki/esa-worldcover-tokyo-2021-100m/resolve/6f006f64483b65b20f06c775b87db7a8d57a6fda/data/parquet/esa_worldcover_tokyo_2021_v200_100m.parquet", None),
}


def fetch_tables():
    con = duckdb.connect()
    con.execute("install spatial; load spatial; install httpfs; load httpfs")
    for name, (url, sql) in SRC.items():
        out = ART / f"{name}.parquet"
        if out.exists():
            continue
        con.execute(f"create or replace view src as select * from '{url}'")
        q = sql or "select * from src"
        con.execute(f"copy ({q}) to '{out}' (format parquet)")
        n = con.execute(f"select count(*) from '{out}'").fetchone()[0]
        print(name, n)


def tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def fetch_dem(z=15, margin_deg=0.02):
    """GSI DEM5A tiles over the wards' bounding box. 404 means no tile (sea) and is counted, not fatal."""
    con = duckdb.connect()
    con.execute("load spatial")
    minx, miny, maxx, maxy = con.execute(f"select min(st_xmin(geometry)), min(st_ymin(geometry)), max(st_xmax(geometry)), max(st_ymax(geometry)) from '{ART / 'wards.parquet'}'").fetchone()
    x0, y1 = tile(minx - margin_deg, miny - margin_deg, z)
    x1, y0 = tile(maxx + margin_deg, maxy + margin_deg, z)
    d = ART / f"dem5a_z{z}"
    d.mkdir(exist_ok=True)
    got = missing = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            f = d / f"{x}_{y}.txt"
            if f.exists() or (d / f"{x}_{y}.404").exists():
                continue
            url = f"https://cyberjapandata.gsi.go.jp/xyz/dem5a/{z}/{x}/{y}.txt"
            try:
                f.write_bytes(urllib.request.urlopen(url, timeout=60).read())
                got += 1
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                (d / f"{x}_{y}.404").write_text("")
                missing += 1
            time.sleep(0.1)
    print("dem tiles", x0, x1, y0, y1, "fetched", got, "404", missing)


if __name__ == "__main__":
    fetch_tables()
    fetch_dem()

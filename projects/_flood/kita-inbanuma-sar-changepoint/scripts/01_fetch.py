"""Fetch the inputs into artifacts/_flood/kita-inbanuma-sar-changepoint/raw/.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with pyproj python scripts/01_fetch.py

- Sentinel-1 RTC (Planetary Computer, sentinel-1-rtc): every Sentinel-1C item of relative orbits 39 and 141 over the
  box between 2026-03-01 and 2026-10-31, VV and VH, cut to the box on their own grid (EPSG:32654, 10 m). The search
  result is saved as rtc_items.json.
- GSI elevation tiles DEM5A (dem5a, z15) and DEM10B (dem, z14) over the box, as text (404 kept as .404).
- ESA WorldCover 2021 (Planetary Computer, esa-worldcover) cut to the box (EPSG:4326).
- The GSI outlines, gsi-inundation-estimate-kita-inbanuma-jp-2026-10 at a pinned revision.
Every file is listed in raw/MANIFEST.json with its source URL (without the SAS token), bytes and sha256.
Files already there are not fetched again.
"""
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = ROOT / "artifacts/_flood/kita-inbanuma-sar-changepoint/raw"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
HF = ("https://huggingface.co/datasets/yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10/resolve/"
      "e760fbab7cdad6bc7de9adf78320cf3eca7ff288/parquet/inundation_kita_inbanuma.parquet")
CENTRE = (140.2582, 35.8063)  # centroid of the union of the four outlines (same as kita-inbanuma-sar-replication)
HALF = (13500, 8500)  # half width and height of the analysis box in m
UTM = "EPSG:32654"
ORBITS = (39, 141)
PERIOD = "2026-03-01T00:00:00Z/2026-10-31T23:59:59Z"
PLATFORM = "sentinel-1c"


def box_utm():
    x, y = Transformer.from_crs("EPSG:4326", UTM, always_xy=True).transform(*CENTRE)
    return x - HALF[0], y - HALF[1], x + HALF[0], y + HALF[1]


def lonlat_box(b, margin=0.005):
    t = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    xs, ys = t.transform([b[0], b[2], b[0], b[2]], [b[1], b[1], b[3], b[3]])
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def get(url, data=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"content-type": "application/json"} if data else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            time.sleep(3 * (i + 1))
        except urllib.error.URLError:
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token(href):
    account = href.split("//")[1].split(".")[0]
    container = href.split("/")[3]
    return json.loads(get(f"{SAS}/{account}/{container}"))["token"]


def cut(href, tok, box_crs, path):
    """Write the window of a COG covering box_crs (in the COG's CRS) to path, on the COG's own grid."""
    with rasterio.open(f"{href}?{tok}") as src:
        w = from_bounds(*box_crs, transform=src.transform).round_offsets().round_lengths()
        data = src.read(window=w, boundless=True, fill_value=src.nodata)
        prof = src.profile.copy()
        prof.update(width=int(w.width), height=int(w.height), transform=src.window_transform(w),
                    driver="GTiff", compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    tmp = path.with_suffix(".part")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(data)
    tmp.rename(path)


def search_rtc(lb):
    q = {"collections": ["sentinel-1-rtc"], "bbox": list(lb), "datetime": PERIOD, "limit": 500,
         "query": {"platform": {"eq": PLATFORM}, "sat:relative_orbit": {"in": list(ORBITS)}}}
    feats = json.loads(get(f"{STAC}/search", data=json.dumps(q).encode()))["features"]
    return sorted(feats, key=lambda f: f["properties"]["datetime"])


def tile_range(lb, z):
    def xy(lon, lat):
        n = 2 ** z
        return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    x0, y0 = xy(lb[0], lb[3])
    x1, y1 = xy(lb[2], lb[1])
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def main():
    (RAW / "rtc").mkdir(parents=True, exist_ok=True)
    manifest = []
    box = box_utm()
    lb = lonlat_box(box)
    print("box", [round(v) for v in box], [round(v, 4) for v in lb])

    items_path = RAW / "rtc_items.json"
    if not items_path.exists():
        items_path.write_text(json.dumps(search_rtc(lb)), encoding="utf-8")
    items = json.loads(items_path.read_text(encoding="utf-8"))
    manifest.append({"path": items_path.name, "url": f"{STAC}/search", "query": {"datetime": PERIOD, "orbits": ORBITS,
                                                                                  "platform": PLATFORM}})
    jobs = []
    for it in items:
        p = it["properties"]
        assert p["proj:epsg"] == 32654 and p["platform"] == PLATFORM, it["id"]
        for pol in ("vv", "vh"):
            path = RAW / "rtc" / f"o{p['sat:relative_orbit']}_{p['datetime'][:10]}_{pol}.tif"
            jobs.append((it["assets"][pol]["href"], path))
            manifest.append({"path": str(path.relative_to(RAW)), "url": it["assets"][pol]["href"], "item": it["id"]})
    todo = [j for j in jobs if not j[1].exists()]
    print("rtc items", len(items), "files", len(jobs), "to fetch", len(todo))
    if todo:
        tok = token(todo[0][0])
        with ThreadPoolExecutor(8) as ex:
            for f in [ex.submit(cut, h, tok, box, p) for h, p in todo]:
                f.result()

    wc_path, wc_item_path = RAW / "worldcover_2021.tif", RAW / "worldcover_item.json"
    if not wc_item_path.exists():
        q = json.dumps({"collections": ["esa-worldcover"], "bbox": list(lb), "datetime": "2021-01-01/2021-12-31"}).encode()
        feats = json.loads(get(f"{STAC}/search", data=q))["features"]
        if len(feats) != 1:
            raise RuntimeError(f"expected one WorldCover tile over the box, got {len(feats)}")
        wc_item_path.write_text(json.dumps(feats[0]), encoding="utf-8")
    wc_item = json.loads(wc_item_path.read_text(encoding="utf-8"))
    href = wc_item["assets"]["map"]["href"]
    if not wc_path.exists():
        cut(href, token(href), lb, wc_path)
    manifest += [{"path": wc_item_path.name, "url": f"{STAC}/collections/esa-worldcover/items/{wc_item['id']}"},
                 {"path": wc_path.name, "url": href}]

    for layer, z in (("dem5a", 15), ("dem", 14)):
        d = RAW / layer / str(z)
        d.mkdir(parents=True, exist_ok=True)
        n404 = 0
        for x, y in tile_range(lb, z):
            p, miss = d / f"{x}_{y}.txt", d / f"{x}_{y}.404"
            url = f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{x}/{y}.txt"
            if not p.exists() and not miss.exists():
                try:
                    p.write_bytes(get(url))
                except urllib.error.HTTPError:
                    miss.write_text("404\n", encoding="utf-8")
                time.sleep(0.05)
            if miss.exists():
                n404 += 1
            else:
                manifest.append({"path": str(p.relative_to(RAW)), "url": url})
        print(layer, "tiles", len(tile_range(lb, z)), "404", n404)

    gp = RAW / "inundation_kita_inbanuma.parquet"
    if not gp.exists():
        gp.write_bytes(get(HF))
    manifest.append({"path": gp.name, "url": HF})

    for m in manifest:
        p = RAW / m["path"]
        m.update(bytes=p.stat().st_size, sha256=sha(p))
    (RAW / "MANIFEST.json").write_text(json.dumps({"box_utm": box, "box_lonlat": lb, "files": manifest},
                                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("files", len(manifest))


if __name__ == "__main__":
    main()

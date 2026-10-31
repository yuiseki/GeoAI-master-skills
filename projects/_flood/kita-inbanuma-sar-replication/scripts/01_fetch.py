"""Fetch the inputs of stage A into artifacts/_flood/kita-inbanuma-sar-replication/raw/.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with pyproj python scripts/01_fetch.py

- Sentinel-1 RTC (Planetary Computer, sentinel-1-rtc): VV and VH of 2026-09-12 and 2026-09-24, relative orbit 39,
  cut to the fetch box on their own grid (EPSG:32654, 10 m), as GeoTIFF; the STAC items are saved as JSON.
- GSI elevation tiles DEM5A (dem5a, z15) and DEM10B (dem, z14) over the fetch box, as text (404 kept as .404).
- ESA WorldCover 2021 (Planetary Computer, esa-worldcover) cut to the fetch box (EPSG:4326).
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
from pathlib import Path

import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = ROOT / "artifacts/_flood/kita-inbanuma-sar-replication/raw"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
RTC_ITEMS = {"before": "S1C_IW_GRDH_1SDV_20260912T084126_20260912T084151_009412_012B80_rtc",
             "after": "S1C_IW_GRDH_1SDV_20260924T084127_20260924T084152_009587_01313D_rtc"}
HF = ("https://huggingface.co/datasets/yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10/resolve/"
      "e760fbab7cdad6bc7de9adf78320cf3eca7ff288/parquet/inundation_kita_inbanuma.parquet")
CENTRE = (140.2582, 35.8063)  # centroid of the union of the four outlines (EXPERIMENT_PLAN.md)
HALF = (13500 + 1000, 8500 + 1000)  # half width and height of the analysis box in m, plus a 1 km margin
UTM = "EPSG:32654"


def fetch_box():
    t = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    x, y = t.transform(*CENTRE)
    return x - HALF[0], y - HALF[1], x + HALF[0], y + HALF[1]


def lonlat_box(b):
    t = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    xs, ys = t.transform([b[0], b[2], b[0], b[2]], [b[1], b[1], b[3], b[3]])
    return min(xs), min(ys), max(xs), max(ys)


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            time.sleep(2 * (i + 1))
        except urllib.error.URLError:
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token(href):
    """SAS token for the blob container of href (https://<account>.blob.core.windows.net/<container>/...)."""
    account = href.split("//")[1].split(".")[0]
    container = href.split("/")[3]
    return json.loads(get(f"{SAS}/{account}/{container}"))["token"]


def cut(href, tok, box_crs, path):
    """Write the window of a COG covering box_crs (in the COG's CRS) to path, on the COG's own grid."""
    with rasterio.open(f"{href}?{tok}") as src:
        w = from_bounds(*box_crs, transform=src.transform).round_offsets().round_lengths()
        data = src.read(window=w)
        prof = src.profile.copy()
        prof.update(width=int(w.width), height=int(w.height), transform=src.window_transform(w),
                    driver="GTiff", compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(data)


def tile_range(lb, z):
    def xy(lon, lat):
        n = 2 ** z
        return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    x0, y0 = xy(lb[0], lb[3])
    x1, y1 = xy(lb[2], lb[1])
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    box = fetch_box()
    lb = lonlat_box(box)
    print("fetch box", [round(v) for v in box], [round(v, 4) for v in lb])

    rtc_tok = None
    for role, item_id in RTC_ITEMS.items():
        item_path = RAW / f"rtc_{role}_item.json"
        if not item_path.exists():
            item_path.write_bytes(get(f"{STAC}/collections/sentinel-1-rtc/items/{item_id}"))
        item = json.loads(item_path.read_text(encoding="utf-8"))
        assert item["properties"]["sat:relative_orbit"] == 39 and item["properties"]["proj:epsg"] == 32654
        manifest.append({"path": item_path.name, "url": f"{STAC}/collections/sentinel-1-rtc/items/{item_id}"})
        for pol in ("vv", "vh"):
            p = RAW / f"rtc_{role}_{pol}.tif"
            href = item["assets"][pol]["href"]
            if not p.exists():
                rtc_tok = rtc_tok or token(href)
                cut(href, rtc_tok, box, p)
            manifest.append({"path": p.name, "url": href})

    wc_path = RAW / "worldcover_2021.tif"
    wc_item_path = RAW / "worldcover_item.json"
    if not wc_item_path.exists():
        q = json.dumps({"collections": ["esa-worldcover"], "bbox": list(lb), "datetime": "2021-01-01/2021-12-31"}).encode()
        req = urllib.request.Request(f"{STAC}/search", data=q, headers={"content-type": "application/json"})
        feats = json.loads(urllib.request.urlopen(req, timeout=120).read())["features"]
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
    (RAW / "MANIFEST.json").write_text(json.dumps({"fetch_box_utm": box, "fetch_box_lonlat": lb, "files": manifest},
                                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("files", len(manifest))


if __name__ == "__main__":
    main()

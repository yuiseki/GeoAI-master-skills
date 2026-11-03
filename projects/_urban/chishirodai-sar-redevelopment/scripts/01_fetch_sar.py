"""Fetch the Sentinel-1 RTC series and WorldCover over the box into artifacts/_urban/chishirodai-sar-redevelopment/raw/.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with pyproj python -u scripts/01_fetch_sar.py

- Sentinel-1 RTC (Planetary Computer, sentinel-1-rtc): every item of relative orbit 46 (descending, about 20:43 UTC =
  05:43 JST) over the box from 2014-10-01 to 2026-10-31, all platforms, VV and VH. Each item is cut to the box on its
  own grid (EPSG:32654, 10 m) as rtc/<item id>_<pol>.tif. The search result is saved as rtc_items.json.
- ESA WorldCover 2021 (Planetary Computer, esa-worldcover) cut to the box (EPSG:4326).
Every file is listed in raw/MANIFEST_sar.json with its source URL (without the SAS token), bytes and sha256.
Files already there are not fetched again.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import rasterio
from rasterio.windows import from_bounds

from common import RAW, UTM, box_lonlat, box_utm, get, sha, stac_search, token, STAC

ORBIT = 46
PERIOD = "2014-10-01T00:00:00Z/2026-10-31T23:59:59Z"


def cut(href, tok, box, path):
    """Write the window of a COG covering box (in the COG's CRS) to path, on the COG's own grid."""
    with rasterio.open(f"{href}?{tok}") as src:
        w = from_bounds(*box, transform=src.transform).round_offsets().round_lengths()
        data = src.read(window=w, boundless=True, fill_value=src.nodata)
        prof = src.profile.copy()
        prof.update(width=int(w.width), height=int(w.height), transform=src.window_transform(w),
                    driver="GTiff", compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    tmp = path.with_suffix(".part")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(data)
    tmp.rename(path)


def main():
    (RAW / "rtc").mkdir(parents=True, exist_ok=True)
    box, lb = box_utm(), box_lonlat()
    print("box", box, [round(v, 5) for v in lb])
    items_path = RAW / "rtc_items.json"
    if not items_path.exists():
        feats = stac_search({"collections": ["sentinel-1-rtc"], "bbox": list(lb), "datetime": PERIOD, "limit": 500,
                             "query": {"sat:relative_orbit": {"eq": ORBIT}}})
        feats = sorted(feats, key=lambda f: f["properties"]["datetime"])
        items_path.write_text(json.dumps(feats), encoding="utf-8")
    items = json.loads(items_path.read_text(encoding="utf-8"))
    manifest = [{"path": items_path.name, "url": f"{STAC}/search", "query": {"datetime": PERIOD, "orbit": ORBIT}}]
    jobs = []
    for it in items:
        p = it["properties"]
        assert p["proj:epsg"] == 32654 and p["sat:relative_orbit"] == ORBIT, it["id"]
        for pol in ("vv", "vh"):
            if pol not in it["assets"]:
                print("no asset", it["id"], pol)
                continue
            path = RAW / "rtc" / f"{it['id']}_{pol}.tif"
            jobs.append((it["assets"][pol]["href"], path))
            manifest.append({"path": str(path.relative_to(RAW)), "url": it["assets"][pol]["href"], "item": it["id"]})
    todo = [j for j in jobs if not j[1].exists()]
    print("rtc items", len(items), "files", len(jobs), "to fetch", len(todo), flush=True)
    if todo:
        tok = token(todo[0][0])
        with ThreadPoolExecutor(8) as ex:
            for k, f in enumerate([ex.submit(cut, h, tok, box, p) for h, p in todo]):
                f.result()
                if k % 50 == 0:
                    print("fetched", k, "of", len(todo), flush=True)

    wc_path, wc_item_path = RAW / "worldcover_2021.tif", RAW / "worldcover_item.json"
    if not wc_item_path.exists():
        feats = stac_search({"collections": ["esa-worldcover"], "bbox": list(lb), "datetime": "2021-01-01/2021-12-31"})
        if len(feats) != 1:
            raise RuntimeError(f"expected one WorldCover tile over the box, got {len(feats)}")
        wc_item_path.write_text(json.dumps(feats[0]), encoding="utf-8")
    wc_item = json.loads(wc_item_path.read_text(encoding="utf-8"))
    href = wc_item["assets"]["map"]["href"]
    if not wc_path.exists():
        m = 0.005
        cut(href, token(href), (lb[0] - m, lb[1] - m, lb[2] + m, lb[3] + m), wc_path)
    manifest += [{"path": wc_item_path.name, "url": f"{STAC}/collections/esa-worldcover/items/{wc_item['id']}"},
                 {"path": wc_path.name, "url": href}]
    for m in manifest:
        p = RAW / m["path"]
        m.update(bytes=p.stat().st_size, sha256=sha(p))
    (RAW / "MANIFEST_sar.json").write_text(json.dumps({"box_utm": box, "box_lonlat": lb, "crs": UTM, "files": manifest},
                                                      ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("files", len(manifest))


if __name__ == "__main__":
    main()

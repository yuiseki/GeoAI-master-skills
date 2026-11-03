"""Fetch the Sentinel-1 RTC scenes of the plan and WorldCover 2021 over the box into artifacts/.../raw/.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with pyproj python -u scripts/01_fetch_sar.py

- Sentinel-1 RTC (Planetary Computer, sentinel-1-rtc): the items of relative orbits 46 and 39 on the dates of
  common.SCENES, VV and VH, each cut to box_utm() as rtc/<item id>_<pol>.tif. Every item must be EPSG:32654 with a
  10 m grid whose origin is on a multiple of 10 m, so that all cuts share one grid (the script stops otherwise).
- ESA WorldCover 2021 (esa-worldcover, v200) cut to the box with a margin (EPSG:4326).
Files already there are not fetched again. raw/MANIFEST_sar.json lists every file with its URL (no token), bytes, sha256.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import rasterio
import rasterio.errors
from rasterio.windows import from_bounds

from common import BOX_LONLAT, RAW, SCENES, STAC, UTM, box_utm, sha, stac_search, token


def cut(href, tok, box, path, tries=4):
    for i in range(tries):
        try:
            return cut_once(href, tok, box, path)
        except rasterio.errors.RasterioIOError as e:
            print("retry", i + 1, path.name, e, flush=True)
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"failed after {tries} tries: {path.name}")


def cut_once(href, tok, box, path):
    with rasterio.open(f"{href}?{tok}") as src:
        t = src.transform
        if src.crs.to_epsg() == 32654 and not (t.a == 10 and t.e == -10 and t.c % 10 == 0 and t.f % 10 == 0):
            raise RuntimeError(f"grid not on 10 m: {href} {t}")
        w = from_bounds(*box, transform=t).round_offsets().round_lengths()
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
    box = box_utm()
    items_path = RAW / "rtc_items.json"
    if not items_path.exists():
        feats = stac_search({"collections": ["sentinel-1-rtc"], "bbox": list(BOX_LONLAT),
                             "datetime": "2019-07-15T00:00:00Z/2019-11-05T00:00:00Z", "limit": 200})
        items_path.write_text(json.dumps(sorted(feats, key=lambda f: f["properties"]["datetime"])), encoding="utf-8")
    items = json.loads(items_path.read_text(encoding="utf-8"))
    want = {(o, d) for o, sc in SCENES.items() for _, d in sc}
    use = [it for it in items if (it["properties"]["sat:relative_orbit"], it["properties"]["datetime"][:10]) in want]
    found = {(it["properties"]["sat:relative_orbit"], it["properties"]["datetime"][:10]) for it in use}
    if found != want:
        raise RuntimeError(f"scenes without an item: {sorted(want - found)}")
    manifest = [{"path": items_path.name, "url": f"{STAC}/search", "bbox": BOX_LONLAT}]
    jobs = []
    for it in use:
        assert it["properties"]["proj:epsg"] == 32654, it["id"]
        for pol in ("vv", "vh"):
            path = RAW / "rtc" / f"{it['id']}_{pol}.tif"
            jobs.append((it["assets"][pol]["href"], path))
            manifest.append({"path": str(path.relative_to(RAW)), "url": it["assets"][pol]["href"], "item": it["id"]})
    todo = [j for j in jobs if not j[1].exists()]
    print("items", len(use), "files", len(jobs), "to fetch", len(todo), "box", box, flush=True)
    if todo:
        tok = token(todo[0][0])
        with ThreadPoolExecutor(8) as ex:
            for k, f in enumerate([ex.submit(cut, h, tok, box, p) for h, p in todo]):
                f.result()
                print("fetched", k + 1, "of", len(todo), flush=True)

    wc_path, wc_item_path = RAW / "worldcover_2021.tif", RAW / "worldcover_item.json"
    if not wc_item_path.exists():
        feats = stac_search({"collections": ["esa-worldcover"], "bbox": list(BOX_LONLAT),
                             "datetime": "2021-01-01/2021-12-31"})
        if len(feats) != 1:
            raise RuntimeError(f"expected one WorldCover tile over the box, got {len(feats)}")
        wc_item_path.write_text(json.dumps(feats[0]), encoding="utf-8")
    wc_item = json.loads(wc_item_path.read_text(encoding="utf-8"))
    href = wc_item["assets"]["map"]["href"]
    if not wc_path.exists():
        m, (w, s, e, n) = 0.01, BOX_LONLAT
        cut(href, token(href), (w - m, s - m, e + m, n + m), wc_path)
    manifest += [{"path": wc_item_path.name, "url": f"{STAC}/collections/esa-worldcover/items/{wc_item['id']}"},
                 {"path": wc_path.name, "url": href}]
    for m in manifest:
        p = RAW / m["path"]
        m.update(bytes=p.stat().st_size, sha256=sha(p))
    (RAW / "MANIFEST_sar.json").write_text(json.dumps({"box_utm": box, "box_lonlat": BOX_LONLAT, "crs": UTM,
                                                       "files": manifest}, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    print("files", len(manifest))


if __name__ == "__main__":
    main()

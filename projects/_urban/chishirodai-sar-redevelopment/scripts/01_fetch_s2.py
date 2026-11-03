"""Fetch small Sentinel-2 L2A windows around the site, for an optical dating of the demolition independent of SAR.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with pyproj python -u scripts/01_fetch_s2.py

- Planetary Computer sentinel-2-l2a, MGRS tile 54SVE, 2017-01-01 to 2026-10-31, scene cloud cover below 60 %.
- For each item: B02, B03, B04, B08 (10 m) and B11, B12, SCL (20 m, read onto the 10 m window by nearest), over the
  outline of labels/site.geojson plus 300 m, on the 10 m grid of the tile (EPSG:32654). Saved as raw/s2/<item id>.npz
  with the digital numbers as stored (uint16) and the item's s2:processing_baseline (from 04.00 the stored values carry
  an offset of +1000; 03_s2.py removes it).
- The search result is saved as raw/s2_items.json; raw/MANIFEST_s2.json lists the files with sha256.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from common import HERE, RAW, sha, stac_search, token, STAC

BANDS = ("B02", "B03", "B04", "B08", "B11", "B12", "SCL")
PERIOD = "2017-01-01T00:00:00Z/2026-10-31T23:59:59Z"


def site_box(margin=300):
    fc = json.loads((HERE.parent / "labels/site.geojson").read_text(encoding="utf-8"))
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    t = Transformer.from_crs("EPSG:4326", "EPSG:32654", always_xy=True)
    xs, ys = t.transform([p[0] for p in ring], [p[1] for p in ring])
    x0, y0 = (min(xs) - margin) // 10 * 10, (min(ys) - margin) // 10 * 10
    x1, y1 = (max(xs) + margin) // 10 * 10 + 10, (max(ys) + margin) // 10 * 10 + 10
    return x0, y0, x1, y1


def fetch(it, tok, box):
    path = RAW / "s2" / f"{it['id']}.npz"
    if path.exists():
        return path
    out, ref = {}, None
    for b in BANDS:
        href = it["assets"][b]["href"]
        with rasterio.open(f"{href}?{tok}") as src:
            if ref is None:
                w = from_bounds(*box, transform=src.transform).round_offsets().round_lengths()
                ref = (int(round(w.height)), int(round(w.width)))
                if src.res != (10.0, 10.0):
                    raise RuntimeError(f"first band is not 10 m: {b}")
                out["transform"] = np.array(src.window_transform(w))[:6]
            w = from_bounds(*box, transform=src.transform)
            out[b] = src.read(1, window=w, out_shape=ref, resampling=Resampling.nearest, boundless=True, fill_value=0)
    out["processing_baseline"] = np.array(it["properties"].get("s2:processing_baseline", ""))
    out["datetime"] = np.array(it["properties"]["datetime"])
    tmp = path.with_suffix(".part.npz")
    np.savez_compressed(tmp, **out)
    tmp.rename(path)
    return path


def main():
    (RAW / "s2").mkdir(parents=True, exist_ok=True)
    box = site_box()
    print("box", box)
    items_path = RAW / "s2_items.json"
    if not items_path.exists():
        t = Transformer.from_crs("EPSG:32654", "EPSG:4326", always_xy=True)
        lon, lat = t.transform((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        feats = stac_search({"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [lon, lat]},
                             "datetime": PERIOD, "limit": 1000,
                             "query": {"eo:cloud_cover": {"lt": 60}, "s2:mgrs_tile": {"eq": "54SVE"}}})
        items_path.write_text(json.dumps(sorted(feats, key=lambda f: f["properties"]["datetime"])), encoding="utf-8")
    items = json.loads(items_path.read_text(encoding="utf-8"))
    print("items", len(items), flush=True)
    tok = token(items[0]["assets"]["B02"]["href"])
    with ThreadPoolExecutor(8) as ex:
        paths = []
        for k, f in enumerate([ex.submit(fetch, it, tok, box) for it in items]):
            paths.append(f.result())
            if k % 100 == 0:
                print("fetched", k, flush=True)
    manifest = [{"path": items_path.name, "url": f"{STAC}/search", "query": {"datetime": PERIOD, "mgrs": "54SVE",
                                                                              "cloud_cover_lt": 60}}]
    manifest += [{"path": str(p.relative_to(RAW)), "item": p.stem, "bytes": p.stat().st_size, "sha256": sha(p)}
                 for p in paths]
    (RAW / "MANIFEST_s2.json").write_text(json.dumps({"box_utm": box, "files": manifest}, indent=1) + "\n",
                                          encoding="utf-8")
    print("files", len(manifest))


if __name__ == "__main__":
    main()

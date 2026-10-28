"""Landsat 5 TM Collection 2 Level-2 around the 102 Dryad beech sites (EXPERIMENT_PLAN.md, B0).

Pixels whose centre lies within 300 m of a site, in the scene's own UTM grid. Per pixel, Collection 2 QA marks:
fill (qa_pixel bit 0), cloud (bit 1 dilated or bit 3), cloud shadow (bit 4), snow (bit 5), saturation of the bands
used (qa_radsat bits 2, 3, 4 for TM bands 3, 4, 5) or a dropped pixel (bit 9), and a DN of red, nir08 or swir16
outside the USGS valid range 7273-43636. Water (bit 7) is counted but kept. Reflectance = DN * 0.0000275 - 0.2.
NDVI and NDMI are computed per pixel; the acquisition value is the median over valid pixels.

Stages (from repository root; the outcome ranks are never read):
    uvx --from 'duckdb>=1.5.5' --with rasterio --with pyproj --with shapely --with pandas --with pyarrow python \
      projects/beech-masting-satellite-proxy/scripts/landsat.py search artifacts/beech-masting-satellite-proxy
    ... landsat.py pixels artifacts/beech-masting-satellite-proxy      (reads the COG windows, resumable)
    ... landsat.py table artifacts/beech-masting-satellite-proxy       (pixels -> site x acquisition table)
"""

import argparse
import json
import math
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

RADIUS_M = 300.0
PIX = 30.0
HALF = 11  # window half width in pixels: 300 m is 10 pixels, plus one for the centre offset
SCALE, OFFSET = 0.0000275, -0.2
VALID_DN = (7273, 43636)
BANDS = ["red", "nir08", "swir16", "qa_pixel", "qa_radsat"]
YEARS = range(1989, 2009)
WINDOWS = {"spring": ("04-01", "05-31"), "summer": ("07-01", "08-31")}
DRYAD = "hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
REASONS = ["fill", "cloud", "shadow", "snow", "saturated", "out_of_range", "water"]


def disk(transform, x, y, radius=RADIUS_M):
    """Window around (x, y) and, per window pixel, the offset of its centre from the site and whether it is
    within radius. transform: affine of the scene (north up, PIX m)."""
    from rasterio.windows import Window

    col = int(math.floor((x - transform.c) / transform.a))
    row = int(math.floor((y - transform.f) / transform.e))
    win = Window(col - HALF, row - HALF, 2 * HALF + 1, 2 * HALF + 1)
    cc = np.arange(win.col_off, win.col_off + win.width)
    rr = np.arange(win.row_off, win.row_off + win.height)
    cx = transform.c + (cc + 0.5) * transform.a
    cy = transform.f + (rr + 0.5) * transform.e
    dx, dy = np.meshgrid(cx - x, cy - y)
    return win, dx, dy, np.hypot(dx, dy) <= radius


def reasons(qa, rad, red, nir, swir):
    """Per pixel 0/1 arrays for each exclusion reason, water, and valid."""
    qa, rad = np.asarray(qa, np.int64), np.asarray(rad, np.int64)
    bit = lambda a, b: (a >> b) & 1  # noqa: E731
    out = {"fill": bit(qa, 0), "cloud": bit(qa, 1) | bit(qa, 3), "shadow": bit(qa, 4), "snow": bit(qa, 5),
           "saturated": bit(rad, 2) | bit(rad, 3) | bit(rad, 4) | bit(rad, 9), "water": bit(qa, 7)}
    rng = np.zeros(qa.shape, np.int64)
    for b in (red, nir, swir):
        b = np.asarray(b)
        rng |= ((b < VALID_DN[0]) | (b > VALID_DN[1])).astype(np.int64)
    out["out_of_range"] = rng
    bad = out["fill"] | out["cloud"] | out["shadow"] | out["snow"] | out["saturated"] | out["out_of_range"]
    out["valid"] = 1 - bad
    return out


def aggregate(red, nir, swir, qa, rad):
    """One acquisition at one site: pixel counts by reason and medians over the valid pixels."""
    r = reasons(qa, rad, red, nir, swir)
    v = r["valid"].astype(bool)
    out = {"n_pixels": int(len(v)), "n_valid": int(v.sum())}
    for k in REASONS:
        out[f"n_{k}"] = int(r[k].sum())
    sr = {k: np.asarray(b, float)[v] * SCALE + OFFSET for k, b in (("red", red), ("nir08", nir), ("swir16", swir))}
    if v.any():
        out["red"], out["nir08"], out["swir16"] = (float(np.median(sr[k])) for k in ("red", "nir08", "swir16"))
        out["ndvi"] = float(np.median((sr["nir08"] - sr["red"]) / (sr["nir08"] + sr["red"])))
        out["ndmi"] = float(np.median((sr["nir08"] - sr["swir16"]) / (sr["nir08"] + sr["swir16"])))
    else:
        out.update({k: math.nan for k in ("red", "nir08", "swir16", "ndvi", "ndmi")})
    return out


def dedupe(df):
    """One row per site and date: the scene with the most valid pixels, ties to the smaller item id."""
    d = df.sort_values(["ID", "date", "n_valid", "item_id"], ascending=[True, True, False, True])
    return d.drop_duplicates(["ID", "date"], keep="first").reset_index(drop=True)


# ---- I/O ----

def load_sites():
    import duckdb

    con = duckdb.connect()
    con.sql("install httpfs; load httpfs")
    s = con.sql(f"""select ID, Location region, Latitude lat, Longitude lon from '{DRYAD}study_sites.parquet'
                    order by ID""").df()
    if len(s) != 102:
        raise ValueError("expected 102 sites")
    return s


def post(body, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(f"{STAC}/search", json.dumps(body).encode(), {"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def search(art):
    sites = load_sites()
    sites.to_parquet(art / "sites.parquet", index=False)
    pts = {"type": "MultiPoint", "coordinates": sites[["lon", "lat"]].to_numpy().tolist()}
    items = []
    for y in YEARS:
        for season, (a, b) in WINDOWS.items():
            body = {"collections": ["landsat-c2-l2"], "intersects": pts, "limit": 1000,
                    "datetime": f"{y}-{a}T00:00:00Z/{y}-{b}T23:59:59Z", "query": {"platform": {"eq": "landsat-5"}}}
            feats = post(body)["features"]
            if len(feats) >= 1000:
                raise RuntimeError("page limit reached")
            for f in feats:
                p = f["properties"]
                items.append({"item_id": f["id"], "datetime": p["datetime"], "season": season, "year": y,
                              "platform": p["platform"], "tier": p["landsat:collection_category"],
                              "wrs_path": p["landsat:wrs_path"], "wrs_row": p["landsat:wrs_row"],
                              "epsg": p["proj:epsg"], "transform": json.dumps(p["proj:transform"]),
                              "cloud_cover": p.get("eo:cloud_cover"), "cloud_cover_land": p.get("landsat:cloud_cover_land"),
                              "sun_elevation": p.get("view:sun_elevation"), "geometry": json.dumps(f["geometry"]),
                              **{f"href_{k}": f["assets"][k]["href"] for k in BANDS}})
            print(y, season, len(feats), flush=True)
    df = pd.DataFrame(items)
    if df.item_id.duplicated().any():
        raise RuntimeError("duplicate items")
    df.to_parquet(art / "items.parquet", index=False)
    print(len(df), df.tier.value_counts().to_dict())


class Token:
    """One anonymous SAS token shared by the threads, renewed after 30 minutes or when a read was refused."""

    def __init__(self):
        import threading

        self.value, self.t, self.lock = None, 0.0, threading.Lock()

    def get(self, stale=None):
        with self.lock:
            if self.value is None or self.value == stale or time.time() - self.t > 1800:
                for i in range(6):
                    try:
                        d = json.load(urllib.request.urlopen(
                            "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2", timeout=60))
                        break
                    except Exception:  # noqa: BLE001
                        if i == 5:
                            raise
                        time.sleep(15 * (i + 1))
                self.value, self.t = d["token"], time.time()
            return self.value


def sites_in(item, sites):
    from shapely.geometry import Point, shape

    g = shape(json.loads(item["geometry"]))
    return sites[[g.contains(Point(lo, la)) for lo, la in zip(sites.lon, sites.lat)]]


def read_item(item, sites, token, out_dir):
    import rasterio
    from affine import Affine
    from pyproj import Transformer

    out = out_dir / f"{item['item_id']}.parquet"
    if out.exists():
        return "skip", 0
    inside = sites_in(item, sites)
    t = json.loads(item["transform"])
    aff = Affine(*t[:6])
    xs, ys = Transformer.from_crs(4326, int(item["epsg"]), always_xy=True).transform(inside.lon.to_numpy(),
                                                                                    inside.lat.to_numpy())
    rows = []
    tok = None
    for attempt in range(4):
        try:
            tok = token.get(stale=tok if attempt else None)
            srcs = {k: rasterio.open(item[f"href_{k}"] + "?" + tok) for k in BANDS}
            try:
                for k, s in srcs.items():
                    if tuple(s.transform)[:6] != tuple(aff)[:6]:
                        raise RuntimeError(f"{item['item_id']} {k}: transform differs from the item")
                rows = []
                for sid, x, y in zip(inside.ID, xs, ys):
                    win, dx, dy, m = disk(aff, x, y)
                    vals = {k: s.read(1, window=win, boundless=True, fill_value=(1 if k == "qa_pixel" else 0))
                            for k, s in srcs.items()}
                    rows.append(pd.DataFrame({"item_id": item["item_id"], "ID": sid,
                                              "dx": np.round(dx[m], 3), "dy": np.round(dy[m], 3),
                                              **{k: v[m].astype(np.uint16) for k, v in vals.items()}}))
            finally:
                for s in srcs.values():
                    s.close()
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            print("retry", item["item_id"], repr(e)[:200], flush=True)
            time.sleep(10 * (attempt + 1))
    df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["item_id", "ID", "dx", "dy"] + BANDS)
    tmp = out.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.rename(out)
    return "done", len(inside)


def pixels(art, workers):
    items = pd.read_parquet(art / "items.parquet")
    sites = pd.read_parquet(art / "sites.parquet")
    out_dir = art / "pixels"
    out_dir.mkdir(parents=True, exist_ok=True)
    token = Token()
    failed = []
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(read_item, r, sites, token, out_dir): r["item_id"] for r in items.to_dict("records")}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                status, k = f.result()
            except Exception as e:  # noqa: BLE001
                failed.append({"item_id": futs[f], "error": repr(e)[:500]})
                status, k = "FAILED", 0
            if n % 25 == 0 or status == "FAILED":
                print(n, len(futs), status, futs[f], k, round(time.time() - t0), flush=True)
    (art / "pixels_failed.json").write_text(json.dumps(failed, indent=1) + "\n")
    print("failed", len(failed), flush=True)
    if failed:
        sys.exit(1)


def table(art):
    """Site x acquisition table from the saved pixels (before the duplicate-date choice)."""
    items = pd.read_parquet(art / "items.parquet").set_index("item_id")
    px = pd.concat([pd.read_parquet(p) for p in sorted((art / "pixels").glob("*.parquet"))], ignore_index=True)
    rows = []
    for (iid, sid), g in px.groupby(["item_id", "ID"], sort=True):
        a = aggregate(g.red.to_numpy(), g.nir08.to_numpy(), g.swir16.to_numpy(), g.qa_pixel.to_numpy(),
                      g.qa_radsat.to_numpy())
        it = items.loc[iid]
        rows.append({"ID": int(sid), "item_id": iid, "datetime": it.datetime, "date": it.datetime[:10],
                     "year": int(it.year), "season": it.season, "tier": it.tier, "wrs_path": it.wrs_path,
                     "wrs_row": it.wrs_row, **a})
    df = pd.DataFrame(rows)
    df.to_parquet(art / "site_acquisitions.parquet", index=False)
    px.to_parquet(art / "pixels.parquet", index=False)
    print(len(px), "pixels", len(df), "site x acquisition rows", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["search", "pixels", "table"])
    ap.add_argument("art", type=Path)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    a.art.mkdir(parents=True, exist_ok=True)
    {"search": lambda: search(a.art), "pixels": lambda: pixels(a.art, a.workers), "table": lambda: table(a.art)}[a.stage]()


if __name__ == "__main__":
    main()

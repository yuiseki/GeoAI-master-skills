"""Check, on the GSI 5 m DEM, whether the pond chains in report.md are connected by the flow of water.

For each system: fetch the DEM5A z15 tiles around it (cached under artifacts/), mosaic, fill the water surfaces
(DEM5A masks them as 'e'), reproject to UTM 53N at 5 m, route with terrain-hydrology's hydro.flow (priority flood,
then steepest D8), follow the flow path down from the head pond's ledger point, and list every ledger pond in the box
whose point lies near that path. Writes outputs/verify_routing.json.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 \
  -p CPUQuota=400% -- uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with duckdb \
  --with scipy python scripts/verify_cascade_routing.py
"""

import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

import duckdb
import numpy as np
import rasterio
from rasterio.transform import from_bounds as tr_from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds
from pyproj import Transformer
from scipy import ndimage

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = PROJECT.parents[2]
sys.path.insert(0, str(REPO / ".agents/skills/terrain-hydrology/scripts"))
from hydro import flow  # noqa: E402

CACHE = REPO / "artifacts/_tameike/cascade-dam-break-routing/dem5a"
TAMEIKE = ("https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03/resolve/"
           "ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet")
Z = 15
DST_CRS = "EPSG:32653"
CELL = 5.0

# Boxes (lon0, lat0, lon1, lat1) around each chain of report.md, and its head pond picked by ledger name and place.
SYSTEMS = {
    "matsunaga": dict(box=(133.225, 34.462, 133.275, 34.505), head=("松永溜池", 34.4811, 133.2497),
                      claimed=["二六池", "かがつ池", "下池", "昌源寺池"]),
    "manno": dict(box=(133.835, 34.135, 133.895, 34.195), head=("満濃池", 34.1650, 133.8661),
                  claimed=["前谷下池", "神田良池"]),
    "kaminagi": dict(box=(134.800, 34.440, 134.830, 34.468), head=("上那木池", 34.45322, 134.81372),
                     claimed=["下那木池", "下那木新池"]),
    "miyama": dict(box=(134.800, 34.440, 134.830, 34.468), head=("深山池", 34.4535, 134.81725),
                   claimed=["深山下池"]),
}


def tile_xy(lon, lat):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def tile_bounds(x, y):
    n = 2 ** Z
    lon = lambda i: i / n * 360 - 180
    lat = lambda j: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * j / n))))
    return lon(x), lat(y + 1), lon(x + 1), lat(y)


def fetch(x, y):
    """Tile as float32 256x256, NaN for 'e'. None for 404 (no land). Cached as text, as the server returns it."""
    path = CACHE / f"{Z}_{x}_{y}.txt"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(f"https://cyberjapandata.gsi.go.jp/xyz/dem5a/{Z}/{x}/{y}.txt", timeout=30) as r:
                path.write_bytes(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            path.write_text("")
    text = path.read_text().strip()
    if not text:
        return None
    rows = [[np.nan if v == "e" else float(v) for v in line.split(",")] for line in text.splitlines()]
    return np.array(rows, dtype="float32")


def mosaic(box):
    x0, y0 = tile_xy(box[0], box[3])
    x1, y1 = tile_xy(box[2], box[1])
    z = np.full(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256), np.nan, dtype="float32")
    n404 = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            t = fetch(x, y)
            if t is None:
                n404 += 1
                continue
            z[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = t
    w, s, _, _ = tile_bounds(x0, y1)
    _, _, e, n = tile_bounds(x1, y0)
    m = 20037508.342789244
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    (mx0, my0), (mx1, my1) = tr.transform(w, s), tr.transform(e, n)
    return z, tr_from_bounds(mx0, my0, mx1, my1, z.shape[1], z.shape[0]), dict(tiles=(x1 - x0 + 1) * (y1 - y0 + 1), tiles_404=n404)


def fill_water(z):
    """DEM5A masks water as NaN. A NaN hole not touching the mosaic edge is a water surface (or a gap): fill it with
    the lowest valid elevation on its rim, a level lake. Holes touching the edge (sea, missing tiles) stay NaN."""
    nan = np.isnan(z)
    lab, n = ndimage.label(nan)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    out = z.copy()
    filled = 0
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if k in edge:
            continue
        sl = tuple(slice(max(s.start - 1, 0), s.stop + 1) for s in sl)
        hole = lab[sl] == k
        rim = ndimage.binary_dilation(hole) & ~hole & ~nan[sl]
        out[sl][hole] = z[sl][rim].min()
        filled += 1
    return out, filled, int(len(edge))


def ponds_in(box):
    con = duckdb.connect()
    q = f"""select name, municipality, storage_thousand_m3, surface_area_km2, dam_height_m, lat, lon from '{TAMEIKE}'
            where lon between {box[0]} and {box[2]} and lat between {box[1]} and {box[3]}"""
    cur = con.execute(q)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def run(key, spec):
    z3857, tr3857, tiles = mosaic(spec["box"])
    filled_src, n_filled, n_edge = fill_water(z3857)
    bounds = transform_bounds("EPSG:3857", DST_CRS, *rasterio.transform.array_bounds(*z3857.shape, tr3857))
    w = int((bounds[2] - bounds[0]) // CELL)
    h = int((bounds[3] - bounds[1]) // CELL)
    tr = rasterio.transform.from_origin(bounds[0], bounds[3], CELL, CELL)
    z = np.full((h, w), np.nan, dtype="float32")
    reproject(filled_src, z, src_transform=tr3857, src_crs="EPSG:3857", dst_transform=tr, dst_crs=DST_CRS,
              resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
    z = np.where(np.isnan(z), -9999.0, z)
    filled, d8, fd = flow(z, tr)
    upa = fd.upstream_area(unit="km2")

    to = Transformer.from_crs("EPSG:4326", DST_CRS, always_xy=True)
    def cell(lat, lon):
        x, y = to.transform(lon, lat)
        c, r = ~tr * (x, y)
        return int(r), int(c)

    hname, hlat, hlon = spec["head"]
    hr, hc = cell(hlat, hlon)
    # the head pond's ledger point may sit on the water or on the dam: start from the cell with the largest
    # upstream area within 30 m (the lake's outflow cell lies on the lake's own flat)
    win = upa[hr - 6:hr + 7, hc - 6:hc + 7]
    i, j = np.unravel_index(np.nanargmax(win), win.shape)
    start = (hr - 6 + i) * w + (hc - 6 + j)
    ds = fd.idxs_ds
    path = [start]
    while ds[path[-1]] != path[-1]:
        path.append(int(ds[path[-1]]))
    path = np.array(path)
    pr, pc = np.unravel_index(path, (h, w))
    px, py = tr * (pc + 0.5, pr + 0.5)
    dist_along = np.concatenate([[0], np.cumsum(np.hypot(np.diff(px), np.diff(py)))])

    rows = []
    for p in ponds_in(spec["box"]):
        x, y = to.transform(p["lon"], p["lat"])
        d = np.hypot(px - x, py - y)
        k = int(np.argmin(d))
        straight = float(np.hypot(x - px[0], y - py[0]))
        rows.append(dict(name=p["name"], storage_thousand_m3=p["storage_thousand_m3"], surface_area_km2=p["surface_area_km2"],
                         dam_height_m=p["dam_height_m"], lat=p["lat"], lon=p["lon"], straight_m=round(straight),
                         off_path_m=round(float(d[k])), along_path_m=round(float(dist_along[k])),
                         elev_on_path_m=round(float(filled[pr[k], pc[k]]), 2)))
    rows.sort(key=lambda r: r["along_path_m"])
    radius = lambda r: max(30.0, math.sqrt(max(r["surface_area_km2"] or 0, 0) * 1e6 / math.pi))
    on_path = [r for r in rows if r["off_path_m"] <= radius(r) and r["name"] != hname]
    claimed = {n: [r for r in rows if r["name"] == n] for n in spec["claimed"]}
    # the other direction: where does a claimed pond's own flow path meet the head's path?
    hx, hy = to.transform(hlon, hlat)
    head_area = next((r["surface_area_km2"] for r in ponds_in(spec["box"]) if r["name"] == hname), 0) or 0
    head_radius = max(30.0, math.sqrt(head_area * 1e6 / math.pi))
    for rs in claimed.values():
        for r in rs:
            rr, cc = cell(r["lat"], r["lon"])
            q = [rr * w + cc]
            while ds[q[-1]] != q[-1]:
                q.append(int(ds[q[-1]]))
            qr, qc = np.unravel_index(np.array(q), (h, w))
            qx, qy = tr * (qc + 0.5, qr + 0.5)
            r["own_path_min_dist_to_head_m"] = round(float(np.min(np.hypot(qx - hx, qy - hy))))
            # where its path first meets the head's path: 0 m means at the head's start cell (the head's own lake
            # or above), more means the two flows join below the head
            pos = {int(c): k for k, c in enumerate(path)}
            meet = next((pos[int(c)] for c in q if int(c) in pos), None)
            r["joins_head_path_at_m"] = None if meet is None else round(float(dist_along[meet]))
            r["elev_m"] = round(float(filled[rr, cc]), 2)
    last = (int(pr[-1]), int(pc[-1]))
    return dict(system=key, head=hname, tiles=tiles, water_holes_filled=n_filled, edge_nan_regions=n_edge,
                grid=dict(crs=DST_CRS, cell_m=CELL, shape=[h, w]),
                path_cells=len(path), path_length_m=round(float(dist_along[-1])),
                path_end=dict(row=last[0], col=last[1], at_edge=last[0] in (0, h - 1) or last[1] in (0, w - 1),
                              elev_m=round(float(filled[last]), 2)),
                head_radius_m=round(head_radius), head_start_elev_m=round(float(filled[pr[0], pc[0]]), 2),
                ponds_on_path=on_path,
                claimed=[dict(name=n, on_path=any(r in on_path for r in rs),
                              candidates=[{k: r[k] for k in ("lat", "lon", "storage_thousand_m3", "elev_m", "straight_m", "off_path_m", "along_path_m", "own_path_min_dist_to_head_m", "joins_head_path_at_m")} for r in rs])
                         for n, rs in claimed.items()])


if __name__ == "__main__":
    keys = sys.argv[1:] or list(SYSTEMS)
    out = [run(k, SYSTEMS[k]) for k in keys]
    (PROJECT / "outputs").mkdir(exist_ok=True)
    (PROJECT / "outputs/verify_routing.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for o in out:
        print(o["system"], o["head"], "path", o["path_length_m"], "m, end at edge", o["path_end"]["at_edge"],
              "holes filled", o["water_holes_filled"])
        for r in o["ponds_on_path"]:
            print("   on path:", r["name"], r["storage_thousand_m3"], "千m3, along", r["along_path_m"], "m, off", r["off_path_m"], "m")
        for c in o["claimed"]:
            print("   claimed", c["name"], "on_path" if c["on_path"] else "NOT on path", c["candidates"][:3])

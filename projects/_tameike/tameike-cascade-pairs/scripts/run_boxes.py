"""B0, B1, B2 of EXPERIMENT_PLAN.md for each box.

  env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 \
    -p CPUQuota=400% -- uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy \
    --with duckdb python scripts/run_boxes.py [box ...]

Tiles are cached as the server returns them under artifacts/_tameike/tameike-cascade-pairs/<layer>/.
Writes outputs/<box>_ponds.csv, outputs/<box>_nodes.csv and outputs/<box>_summary.json.
"""

import csv
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import duckdb
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_bounds as tr_from_bounds
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

from cascade_pairs import REPO, assign_nodes, cumulative, cumulative_within, downstream_nodes, fill_holes, top_only_in_cum
from hydro import flow

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "outputs"
CACHE = REPO / "artifacts/_tameike/tameike-cascade-pairs"
TAMEIKE = ("https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03/resolve/"
           "ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet")
DST = "EPSG:32653"
BOXES = {  # lon0, lat0, lon1, lat1, fixed in EXPERIMENT_PLAN.md
    "kagawa": (133.78, 34.13, 133.94, 34.27),
    "fukuyama": (133.20, 34.42, 133.36, 34.56),
    "awaji": (134.78, 34.40, 134.94, 34.54),
}
LAYERS = {"dem5a": 15, "dem": 14}
SHARES = (0.05, 0.10, 0.20)
# B0: pairs already traced on DEM5A in cascade-dam-break-routing/outputs/verify_routing.json (upper, lower, lat, lon)
EXPECTED = {"awaji": [(("上那木池", 34.45322), ("下那木新池", 34.45625)), (("深山池", 34.4535), ("深山下池", 34.45433))]}
PLACEHOLDER_STORAGE = 9999.9


def tile_xy(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def fetch(layer, z, x, y):
    path = CACHE / layer / f"{z}_{x}_{y}.txt"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(5):  # GSI sometimes resets the connection: retry with a growing wait, then fail
            try:
                with urllib.request.urlopen(f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{x}/{y}.txt", timeout=30) as r:
                    body = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                body = b""
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if attempt == 4:
                    raise
                time.sleep(2.0 * 2 ** attempt)
        path.write_bytes(body)
        time.sleep(0.1)
    text = path.read_text().strip()
    if not text:
        return None
    return np.array([[np.nan if v == "e" else float(v) for v in line.split(",")] for line in text.splitlines()],
                    dtype="float32")


def mosaic(layer, box):
    z = LAYERS[layer]
    x0, y0 = tile_xy(box[0], box[3], z)
    x1, y1 = tile_xy(box[2], box[1], z)
    arr = np.full(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256), np.nan, dtype="float32")
    n404 = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            t = fetch(layer, z, x, y)
            if t is None:
                n404 += 1
            else:
                arr[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = t
    m = 2 * math.pi * 6378137 / 2 ** z  # tile size in EPSG:3857 metres
    o = math.pi * 6378137
    tr = tr_from_bounds(x0 * m - o, o - (y1 + 1) * m, (x1 + 1) * m - o, o - y0 * m, arr.shape[1], arr.shape[0])
    return arr, tr, dict(tiles=(x1 - x0 + 1) * (y1 - y0 + 1), tiles_404=n404)


def to_utm(arr, tr, grid):
    """Bilinear for the elevation, nearest for where it is NaN, so water holes keep their shape."""
    (h, w), dst_tr = grid
    z = np.full((h, w), np.nan, dtype="float32")
    reproject(np.nan_to_num(arr, nan=-9999.0), z, src_transform=tr, src_crs="EPSG:3857", dst_transform=dst_tr,
              dst_crs=DST, resampling=Resampling.bilinear, src_nodata=-9999.0, dst_nodata=np.nan)
    mask = np.zeros((h, w), dtype="uint8")
    reproject(np.isnan(arr).astype("uint8"), mask, src_transform=tr, src_crs="EPSG:3857", dst_transform=dst_tr,
              dst_crs=DST, resampling=Resampling.nearest)
    z[mask == 1] = np.nan
    return z


def utm_grid(box, cell):
    t = Transformer.from_crs("EPSG:4326", DST, always_xy=True)
    xs, ys = t.transform([box[0], box[2], box[0], box[2]], [box[1], box[1], box[3], box[3]])
    x0, x1 = math.floor(max(xs[0], xs[2]) / 10) * 10, math.floor(min(xs[1], xs[3]) / 10) * 10
    y0, y1 = math.ceil(max(ys[0], ys[1]) / 10) * 10, math.floor(min(ys[2], ys[3]) / 10) * 10
    return (int((y1 - y0) / cell), int((x1 - x0) / cell)), from_origin(x0, y1, cell, cell)


def ponds_in(box):
    con = duckdb.connect()
    cur = con.execute(f"""select source_row, name, municipality, storage_thousand_m3, surface_area_km2, dam_height_m,
                          lat, lon, coord_status from '{TAMEIKE}'
                          where lon between {box[0]} and {box[2]} and lat between {box[1]} and {box[3]}
                          order by source_row""")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def run_grid(z, tr, nodes, lengths=None):
    _, _, fd = flow(np.where(np.isnan(z), -9999.0, z), tr)
    return downstream_nodes(nodes, fd, lengths=lengths, cell=tr.a)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run(key):
    box = BOXES[key]
    t0 = time.time()
    ponds = ponds_in(box)
    (h, w), tr5 = utm_grid(box, 5.0)
    arr, tr3857, tiles5 = mosaic("dem5a", box)
    z5 = to_utm(arr, tr3857, ((h, w), tr5))
    del arr
    filled5, labels = fill_holes(z5)
    del z5
    to = Transformer.from_crs("EPSG:4326", DST, always_xy=True)
    xs, ys = to.transform([p["lon"] for p in ponds], [p["lat"] for p in ponds])
    cols, rows = ~tr5 * (np.array(xs), np.array(ys))
    rows, cols = np.floor(rows).astype(int), np.floor(cols).astype(int)

    result = dict(box=key, bounds_lonlat=box, grid=dict(crs=DST, cell_m=5.0, shape=[h, w]), dem5a=tiles5,
                  n_ponds=len(ponds), holes=int(labels.max()))
    variants = {}
    for dist_m in (30, 60):
        nodes, node_of, how = assign_nodes(labels, rows, cols, max_cells=dist_m / 5.0)
        variants[dist_m] = (nodes, node_of, how)
        result[f"assign_{dist_m}m"] = {k: int((how == k).sum()) for k in ("hole", "point", "outside")}
    nodes, node_of, how = variants[30]

    own = {}
    members = {}
    for p, n in zip(ponds, node_of):
        if n == 0:
            continue
        members.setdefault(int(n), []).append(p)
        v = p["storage_thousand_m3"]
        own[int(n)] = own.get(int(n), 0.0) + (v if v is not None and v != PLACEHOLDER_STORAGE else 0.0)
    result["nodes"] = len(members)
    result["nodes_with_2plus_ponds"] = sum(len(m) > 1 for m in members.values())
    result["ponds_placeholder_storage"] = sum(p["storage_thousand_m3"] == PLACEHOLDER_STORAGE for p in ponds)

    lengths = {}
    down5 = run_grid(filled5, tr5, nodes, lengths)
    cum = cumulative(down5, own)
    # exploratory (decided after the visual check of R003): only the ponds upstream within a flow distance
    result["exploratory_top_only_10pct_within_m"] = {
        str(m): len(top_only_in_cum(own, cumulative_within(down5, own, lengths, m), 0.10)) for m in (500, 1000, 2000)}
    result["pair_length_m_quartiles"] = [round(float(q)) for q in np.percentile(list(lengths.values()), [25, 50, 75])]
    result["nodes_with_downstream_node"] = sum(d is not None for d in down5.values())
    result["top_only_in_cum"] = {str(s): top_only_in_cum(own, cum, s) for s in SHARES}
    result["top_only_in_cum_count"] = {str(s): len(v) for s, v in result["top_only_in_cum"].items()}

    # robustness: 60 m matching
    nodes60, node_of60, _ = variants[60]
    own60 = {}
    for p, n in zip(ponds, node_of60):
        if n:
            v = p["storage_thousand_m3"]
            own60[int(n)] = own60.get(int(n), 0.0) + (v if v is not None and v != PLACEHOLDER_STORAGE else 0.0)
    cum60 = cumulative(run_grid(filled5, tr5, nodes60), own60)
    result["top_only_in_cum_count_60m"] = {str(s): len(top_only_in_cum(own60, cum60, s)) for s in SHARES}

    # B2: 10 m DEM, same water surfaces (the 5 m nodes, max-pooled to 10 m)
    arr10, tr10src, tiles10 = mosaic("dem", box)
    h10, w10 = h // 2, w // 2
    tr10 = from_origin(tr5.c, tr5.f, 10.0, 10.0)
    z10 = to_utm(arr10, tr10src, ((h10, w10), tr10))
    nodes10 = nodes[:h10 * 2, :w10 * 2].reshape(h10, 2, w10, 2).max(axis=(1, 3))
    filled10, _ = fill_holes(z10)
    down10 = run_grid(filled10, tr10, nodes10)
    pairs5 = {(n, d) for n, d in down5.items() if d is not None}
    pairs10 = {(n, d) for n, d in down10.items() if d is not None}
    result["dem10"] = tiles10
    result["pairs_5m"] = len(pairs5)
    result["pairs_10m"] = len(pairs10)
    result["pairs_both"] = len(pairs5 & pairs10)
    result["jaccard_5m_10m"] = round(len(pairs5 & pairs10) / len(pairs5 | pairs10), 3) if pairs5 | pairs10 else None

    def node_named(name, lat):
        for p, n in zip(ponds, node_of):
            if p["name"] == name and abs(p["lat"] - lat) < 1e-4:
                return int(n)
    def below(n):
        out = []
        while down5.get(n) is not None:
            n = down5[n]
            out.append(n)
        return out
    # reproduced: the lower pond is somewhere below the upper (small ponds may sit between them)
    result["expected_pairs"] = [dict(upper=u[0], lower=l[0], upper_node=node_named(*u), lower_node=node_named(*l),
                                     ponds_between=below(node_named(*u)).index(node_named(*l))
                                     if node_named(*l) in below(node_named(*u)) else None,
                                     reproduced=node_named(*l) in below(node_named(*u)))
                                for u, l in EXPECTED.get(key, [])]

    rank = lambda d: {n: i + 1 for i, n in enumerate(sorted(d, key=lambda n: (-d[n], n)))}
    r_own, r_cum = rank(own), rank(cum)
    node_rows = []
    for n in sorted(down5):
        ms = members.get(n, [])
        node_rows.append(dict(node=n, ponds=len(ms), names="|".join(str(m["name"]) for m in ms),
                              source_rows="|".join(str(m["source_row"]) for m in ms),
                              own_thousand_m3=round(own.get(n, 0.0), 3), cum_thousand_m3=round(cum[n], 3),
                              rank_own=r_own[n], rank_cum=r_cum[n], down_node_5m=down5[n] or "",
                              to_down_m=round(lengths[n]) if n in lengths else "",
                              down_node_10m=down10.get(n) or ""))
    write_csv(OUT / f"{key}_nodes.csv", node_rows)
    pond_rows = [dict(source_row=p["source_row"], name=p["name"], municipality=p["municipality"],
                      storage_thousand_m3=p["storage_thousand_m3"], lat=p["lat"], lon=p["lon"],
                      coord_status=p["coord_status"], node=int(n), placed=hw)
                 for p, n, hw in zip(ponds, node_of, how)]
    write_csv(OUT / f"{key}_ponds.csv", pond_rows)
    result["seconds"] = round(time.time() - t0)
    (OUT / f"{key}_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(key, {k: v for k, v in result.items() if k not in ("top_only_in_cum",)}, flush=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for k in sys.argv[1:] or list(BOXES):
        run(k)

"""Context layers for the interactive map, built from the same data as the model (no outside tile server):
a base image (hillshade from the 100 m elevation, tinted by tree cover, water where there is no elevation),
major roads and rivers from the OSM snapshot, municipal boundaries and their names, and the cells with
reports in bear year 2026 (April to September). The base image uses the same Web Mercator frame as risk.png.

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
        --with pandas --with pyarrow --with shapely --with pyproj --with pillow python web_layers.py ART_DIR WEB_DIR
"""

import json
import sys

import numpy as np

import render_maps as rm
from grid import CRS, Grid

OSM = "hf://datasets/yuiseki/osm-japan-src-2026-08@9a9b4a77e89e28a66bf15781644a16b63501f622/parquet/planet_osm_line.parquet"


def hillshade(elev, size, azimuth=315.0, altitude=45.0):
    """0..1 shade of a north-up grid whose row 0 is the south edge."""
    gy, gx = np.gradient(elev, size)  # gy: change toward the north
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, -gy)  # direction the slope faces, from north, clockwise
    az, alt = np.radians(azimuth), np.radians(altitude)
    return np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def geojson_lines(geoms, props, tol, tr):
    import shapely

    feats = []
    for gm, p in zip(geoms, props):
        gm = shapely.simplify(gm, tol)
        if gm.is_empty:
            continue
        for part in getattr(gm, "geoms", [gm]):
            c = np.asarray(part.coords)
            lon, lat = tr.transform(c[:, 0], c[:, 1])
            feats.append({"type": "Feature", "properties": p,
                          "geometry": {"type": "LineString", "coordinates": np.round(np.column_stack([lon, lat]), 5).tolist()}})
    return {"type": "FeatureCollection", "features": feats}


def main():
    import duckdb
    import pandas as pd
    import pyproj
    import shapely
    from PIL import Image

    art, web = sys.argv[1], sys.argv[2]
    meta = json.load(open(f"{art}/grid.json"))
    g = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    elev = np.load(f"{art}/dem.npz")["elev"].astype(float)
    tree = np.nan_to_num(np.load(f"{art}/worldcover.npz")["f10"].astype(float))
    shade = hillshade(np.where(np.isnan(elev), 0.0, elev), g.size)
    # base colour: pale ground, greener with tree cover, darker on the shaded side; water where there is no elevation
    ground = np.array([236, 233, 226], float)
    forest = np.array([190, 210, 182], float)
    base = ground[None, None, :] * (1 - tree[..., None]) + forest[None, None, :] * tree[..., None]
    base = base * (0.62 + 0.38 * shade[..., None])
    base[np.isnan(elev)] = [184, 208, 226]
    base[muni < 0] = base[muni < 0] * 0.85 + 255 * 0.15  # outside the prefecture: faded
    idx = (np.arange(g.ny)[:, None] * g.nx + np.arange(g.nx)[None, :]).astype(np.int64)
    back = pyproj.Transformer.from_crs("EPSG:3857", CRS, always_xy=True)
    xs, ys, _, _ = rm.mercator_frame(g)
    pix = np.vstack([rm.sample_to_pixels(idx, g, xs, ys[i:i + 512], back.transform) for i in range(0, len(ys), 512)])
    flat = base.reshape(-1, 3)
    img = np.full(pix.shape + (3,), 245, dtype=np.uint8)
    ok = pix >= 0
    img[ok] = flat[pix[ok]].astype(np.uint8)
    Image.fromarray(img, "RGB").save(f"{web}/base.jpg", quality=82, optimize=True)
    print("base.jpg", img.shape)

    # roads and rivers from OSM inside the grid's bounding box
    to3857 = pyproj.Transformer.from_crs(CRS, "EPSG:3857", always_xy=True)
    X, Y = to3857.transform([g.x0, g.x0 + g.nx * g.size], [g.y0, g.y0 + g.ny * g.size])
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    rows = con.execute(f"""SELECT highway, waterway, ref, name, ST_AsWKB(way) FROM read_parquet('{OSM}')
        WHERE bbox.xmin <= {max(X)} AND bbox.xmax >= {min(X)} AND bbox.ymin <= {max(Y)} AND bbox.ymax >= {min(Y)}
          AND (highway IN ('motorway','trunk','primary','secondary') OR waterway = 'river')""").fetchall()
    tr6678 = pyproj.Transformer.from_crs("EPSG:3857", CRS, always_xy=True)

    def f(c):
        return np.column_stack(tr6678.transform(c[:, 0], c[:, 1]))

    geoms = shapely.transform(shapely.from_wkb([bytes(r[4]) for r in rows]), f)
    to_ll = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    roads = [(gm, {"kind": r[0]}) for gm, r in zip(geoms, rows) if r[0]]
    rivers = [(gm, {"kind": "river"}) for gm, r in zip(geoms, rows) if r[1] == "river"]
    for name, items in (("roads", roads), ("rivers", rivers)):
        gj = geojson_lines([a for a, _ in items], [b for _, b in items], 25.0, to_ll)
        json.dump(gj, open(f"{web}/{name}.geojson", "w"), separators=(",", ":"))
        print(name, len(items), "lines ->", len(gj["features"]), "features")

    # municipal boundaries and names
    munis = rm.municipal_lines()
    feats, labels = [], []
    for name, gm in munis:
        gm = shapely.simplify(gm, 50.0)
        for part in getattr(gm, "geoms", [gm]):
            c = np.asarray(part.exterior.coords)
            lon, lat = to_ll.transform(c[:, 0], c[:, 1])
            feats.append({"type": "Feature", "properties": {"name": name},
                          "geometry": {"type": "LineString", "coordinates": np.round(np.column_stack([lon, lat]), 5).tolist()}})
        p = gm.representative_point() if not hasattr(gm, "geoms") else max(gm.geoms, key=lambda q: q.area).representative_point()
        lon, lat = to_ll.transform(p.x, p.y)
        labels.append({"name": name, "lon": round(lon, 5), "lat": round(lat, 5)})
    json.dump({"type": "FeatureCollection", "features": feats}, open(f"{web}/municipalities.geojson", "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(labels, open(f"{web}/labels.json", "w"), ensure_ascii=False)

    # cells with reports in bear year 2026 (April to September), at the cell centre
    rep = np.load(f"{art}/reports_by_year.npz")["c2026"]
    iy, ix = np.nonzero((rep > 0) & (muni >= 0))
    lon, lat = to_ll.transform(g.x0 + (ix + 0.5) * g.size, g.y0 + (iy + 0.5) * g.size)
    pts = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"n": int(rep[a, b])}, "geometry": {"type": "Point", "coordinates": [round(x, 5), round(y, 5)]}}
        for a, b, x, y in zip(iy, ix, lon, lat)]}
    json.dump(pts, open(f"{web}/reports2026.geojson", "w"), separators=(",", ":"))
    print("report cells 2026:", len(pts["features"]))


if __name__ == "__main__":
    main()

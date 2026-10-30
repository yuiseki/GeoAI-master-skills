"""Build the grid of the 23 wards and put every input on it.

uv run --with 'duckdb>=1.5.5' --with numpy --with shapely --with pyproj --with pyarrow --with scipy \
    python scripts/02_grid.py SIZE_M [OFFSET_M]

Writes artifacts/tokyo23-flood-record-vs-a31a/grid_<size>[_off<offset>]/:
  cells.parquet         one row per cell whose centre is in a ward: ix, iy, x, y, ward, static features, A31a ranks
  flood_cell_year.parquet  one row per (cell, year) with a record polygon touching the cell
  audit.json            the counts that the steps below check

Coordinates: wards and records are JGD2000 (EPSG:4612) longitude and latitude and are read as JGD2011
(EPSG:6668); the shift in Tokyo is a few centimetres, far below a cell. The grid is EPSG:6677 (plane
rectangular IX), metres. The DEM, the OSM lines (EPSG:3857) and WorldCover (EPSG:4326) are projected to it.
"""
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/grid-risk-mapping/scripts"))
import grid_cells as gc  # noqa: E402

RAW = ROOT / "artifacts/tokyo23-flood-record-vs-a31a/raw"
T_LL = Transformer.from_crs("EPSG:6668", "EPSG:6677", always_xy=True)
T_WM = Transformer.from_crs("EPSG:3857", "EPSG:6677", always_xy=True)


def con():
    c = duckdb.connect()
    c.execute("load spatial")
    return c


def project(geoms, t):
    return shapely.transform(geoms, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))


def read_geoms(c, path, cols, geom="geometry", where="true"):
    rows = c.execute(f"select {cols}, st_aswkb({geom}) from '{path}' where {where}").fetchall()
    return rows, shapely.from_wkb([r[-1] for r in rows])


def main(size, offset=0.0):
    out = ROOT / "artifacts/tokyo23-flood-record-vs-a31a" / (f"grid_{size:g}" + ("" if offset == 0 else f"_off{offset:g}"))
    out.mkdir(parents=True, exist_ok=True)
    c = con()
    audit = {"size": size, "offset": offset}

    # wards and grid
    rows, g = read_geoms(c, RAW / "wards.parquet", "code5, name")
    wards = project(shapely.make_valid(g), T_LL)
    minx, miny, maxx, maxy = shapely.total_bounds(wards)
    grid = gc.Grid.from_bounds(minx - size - offset, miny - size - offset, maxx + size, maxy + size, size)
    grid = gc.Grid(grid.x0 + offset, grid.y0 + offset, grid.nx, grid.ny, size)
    inside = gc.cells_inside(grid, list(wards))
    X, Y = grid.centres()
    sel = inside >= 0
    iy, ix = np.nonzero(sel)
    n = len(ix)
    ward_area = float(shapely.area(shapely.union_all(wards)))
    audit.update(cells=n, cells_area_km2=n * size * size / 1e6, wards_area_km2=ward_area / 1e6, grid=grid.to_dict())
    cols = {"ix": ix, "iy": iy, "x": X[sel], "y": Y[sel], "ward": np.array([rows[k][0] for k in inside[sel]])}

    # DEM5A z15: pixel centres -> cells (mean, std, min, count); 'e' is no value
    acc_s = np.zeros((grid.ny, grid.nx)); acc_q = np.zeros_like(acc_s); acc_n = np.zeros_like(acc_s)
    acc_min = np.full_like(acc_s, np.inf)
    n_pix = n_e = 0
    z = 15
    for f in sorted((RAW / "dem5a_z15").glob("*.txt")):
        tx, ty = map(int, f.stem.split("_"))
        a = np.array([[np.nan if v == "e" else float(v) for v in line.split(",")] for line in f.read_text().strip().splitlines()])
        assert a.shape == (256, 256), f
        n_pix += a.size; n_e += int(np.isnan(a).sum())
        px = (tx * 256 + np.arange(256) + 0.5) / (256 * 2 ** z)
        py = (ty * 256 + np.arange(256) + 0.5) / (256 * 2 ** z)
        mx = (px * 2 - 1) * 20037508.342789244
        my = (1 - py * 2) * 20037508.342789244
        MX, MY = np.meshgrid(mx, my)
        ok = ~np.isnan(a)
        xx, yy = T_WM.transform(MX[ok], MY[ok])
        jx, jy, inb = grid.index(xx, yy)
        v = a[ok][inb]; k = jy[inb] * grid.nx + jx[inb]
        acc_s.ravel()[:] += np.bincount(k, weights=v, minlength=grid.nx * grid.ny)
        acc_q.ravel()[:] += np.bincount(k, weights=v * v, minlength=grid.nx * grid.ny)
        acc_n.ravel()[:] += np.bincount(k, minlength=grid.nx * grid.ny)
        np.minimum.at(acc_min.ravel(), k, v)
    with np.errstate(invalid="ignore", divide="ignore"):
        elev = acc_s / acc_n
        sd = np.sqrt(np.maximum(acc_q / acc_n - elev ** 2, 0))
    elev[acc_n == 0] = np.nan; sd[acc_n == 0] = np.nan
    audit.update(dem_pixels=n_pix, dem_no_value=n_e, cells_without_dem=int((acc_n[sel] == 0).sum()))
    r300 = max(1, round(300 / size / 2 - 0.5)) if size < 300 else 1
    r1000 = max(1, round(1000 / size / 2 - 0.5))
    emin = acc_min.copy(); emin[np.isinf(emin)] = np.nan
    lmin = ndimage.minimum_filter(np.where(np.isnan(emin), np.inf, emin), size=2 * r300 + 1, mode="nearest")
    cols.update(
        elev=elev[sel], slope_sd=sd[sel],
        rel_elev_300=(elev - gc.box_mean(elev, r300))[sel],
        rel_elev_1000=(elev - gc.box_mean(elev, r1000))[sel],
        elev_min_rel=(elev - lmin)[sel],
    )

    # waterways (OSM, EPSG:3857). Distances on a padded grid so that lines outside the wards count.
    wrows, wl = read_geoms(c, RAW / "osm_waterway.parquet", "waterway, tunnel", geom="way")
    wl = project(wl, T_WM)
    pad = 20
    pg = gc.Grid(grid.x0 - pad * size, grid.y0 - pad * size, grid.nx + 2 * pad, grid.ny + 2 * pad, size)

    def dist(lines):
        mark = np.zeros((pg.ny, pg.nx), bool)
        for ln in lines:
            if ln is None or shapely.is_empty(ln):
                continue
            L = shapely.length(ln)
            pts = shapely.line_interpolate_point(ln, np.arange(0, L + size / 5, size / 5))
            px_, py_ = shapely.get_x(pts), shapely.get_y(pts)
            jx, jy, ok = pg.index(px_, py_)
            mark[jy[ok], jx[ok]] = True
        d = ndimage.distance_transform_edt(~mark) * size
        return d[pad:-pad, pad:-pad]

    kinds = np.array([r[0] for r in wrows]); tun = np.array([(r[1] or "") for r in wrows])
    cols["d_waterway"] = dist(wl)[sel]
    open_river = np.isin(kinds, ["river", "canal"]) & ~np.isin(tun, ["yes", "culvert"])
    cols["d_river_open"] = dist(wl[open_river])[sel]
    audit.update(waterways=len(wl), open_rivers=int(open_river.sum()))

    # WorldCover 100 m cells: pixel counts summed into our cells by the WorldCover cell centre
    wc = c.execute(f"select st_x(st_centroid(geometry)) lon, st_y(st_centroid(geometry)) lat, valid_pixels, pixels_10, pixels_50, pixels_80 from '{RAW}/worldcover.parquet'").fetchnumpy()
    assert 139 < np.median(wc["lon"]) < 141 and 35 < np.median(wc["lat"]) < 36, "WorldCover axis order"
    wx, wy = T_LL.transform(wc["lon"], wc["lat"])
    tot, _ = grid.sum_into(wx, wy, wc["valid_pixels"])
    for name, col in [("tree", "pixels_10"), ("built", "pixels_50"), ("water", "pixels_80")]:
        s_, _ = grid.sum_into(wx, wy, wc[col])
        with np.errstate(invalid="ignore", divide="ignore"):
            cols[name] = (s_ / tot)[sel]

    # rain climatology: nearest mainland station's hours >= 30 mm per year in 1976-1996 (stations with 15 or more of those years)
    st = c.execute(f"select station_id, lon, lat from '{RAW}/rain_stations.parquet' where lat > 35.4 and lon < 140.2").fetchall()
    clim = dict(c.execute(f"""select station_id, count(*) filter (where precip_mm >= 30) / count(distinct year(time_end - interval 1 hour))
        from '{RAW}/rain_hourly.parquet' where year(time_end - interval 1 hour) between 1976 and 1996 and precip_mm is not null
        group by 1 having count(distinct year(time_end - interval 1 hour)) >= 15""").fetchall())
    st = [s for s in st if s[0] in clim and clim[s[0]] is not None]
    sx, sy = T_LL.transform([s[1] for s in st], [s[2] for s in st])
    d2 = (cols["x"][:, None] - np.array(sx)[None]) ** 2 + (cols["y"][:, None] - np.array(sy)[None]) ** 2
    nearest = np.argmin(d2, axis=1)
    cols["rain_clim"] = np.array([clim[st[k][0]] for k in nearest])
    cols["rain_station"] = np.array([st[k][0] for k in nearest])
    audit["rain_stations"] = {s[0]: clim[s[0]] for s in st}

    # A31a: max rank of the polygons that hold the cell centre, per category
    arows, ag = read_geoms(c, RAW / "a31a.parquet", "category, class_code")
    ag = project(shapely.make_valid(ag), T_LL)
    cat = np.array([r[0] for r in arows]); code = np.array([r[1] for r in arows])
    pts = shapely.points(cols["x"], cols["y"])
    tree = shapely.STRtree(ag)
    pi, gi = tree.query(pts, predicate="intersects")
    for name in ["maximum", "planned"]:
        m = cat[gi] == name
        best = np.zeros(n, dtype=np.int16)
        np.maximum.at(best, pi[m], code[gi[m]].astype(np.int16))
        cols[f"a31a_{name}"] = best
    audit["a31a_share_maximum"] = float((cols["a31a_maximum"] > 0).mean())
    audit["a31a_share_planned"] = float((cols["a31a_planned"] > 0).mean())

    pq.write_table(pa.table(cols), out / "cells.parquet")

    # flood records: the cells each polygon touches (any overlap) and whether the cell centre is inside
    frows, fg = read_geoms(c, RAW / "flood_record_area.parquet", "year, layer, row, reason")
    fg = project(shapely.make_valid(fg), T_LL)
    cell_index = -np.ones((grid.ny, grid.nx), dtype=np.int64)
    cell_index[iy, ix] = np.arange(n)
    recs = []
    for k, poly in enumerate(fg):
        bx0, by0, bx1, by1 = shapely.bounds(poly)
        jx0, jy0, _ = grid.index(bx0, by0); jx1, jy1, _ = grid.index(bx1, by1)
        jx0, jy0 = max(jx0, 0), max(jy0, 0); jx1, jy1 = min(jx1, grid.nx - 1), min(jy1, grid.ny - 1)
        if jx1 < jx0 or jy1 < jy0:
            continue
        JX, JY = np.meshgrid(np.arange(jx0, jx1 + 1), np.arange(jy0, jy1 + 1))
        JX, JY = JX.ravel(), JY.ravel()
        ci = cell_index[JY, JX]
        keep = ci >= 0
        if not keep.any():
            continue
        JX, JY, ci = JX[keep], JY[keep], ci[keep]
        boxes = shapely.box(grid.x0 + JX * size, grid.y0 + JY * size, grid.x0 + (JX + 1) * size, grid.y0 + (JY + 1) * size)
        shapely.prepare(poly)
        hit = shapely.intersects(poly, boxes)
        area = shapely.area(shapely.intersection(poly, boxes[hit]))
        centre = shapely.contains_xy(poly, grid.x0 + (JX[hit] + 0.5) * size, grid.y0 + (JY[hit] + 0.5) * size)
        reason = frows[k][3] or ""
        for c_, a_, ce in zip(ci[hit], area, centre):
            if a_ > 0:
                recs.append((int(c_), frows[k][0], k, float(a_), bool(ce), "内水" in reason, "溢水" in reason))
    t = pa.table({k: list(v) for k, v in zip(["cell", "year", "poly", "overlap_m2", "centre_in", "naisui", "issui"], zip(*recs))})
    con2 = duckdb.connect()
    con2.register("t", t)
    agg = con2.execute("""select cell, year, count(distinct poly) n_poly, sum(overlap_m2) overlap_m2, bool_or(centre_in) centre_in,
        bool_or(naisui) naisui, bool_or(issui) issui from t group by all order by cell, year""").fetchnumpy()
    agg = pa.table(agg)
    pq.write_table(agg, out / "flood_cell_year.parquet")
    audit.update(record_polygons=len(fg), record_polygons_touching=int(len(set(r[2] for r in recs))), cell_year_rows=agg.num_rows)
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: v for k, v in audit.items() if k not in ("grid", "rain_stations")}, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)

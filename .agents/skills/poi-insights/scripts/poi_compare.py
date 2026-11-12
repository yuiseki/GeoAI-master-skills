"""Compare places (POI) between regions: how many, per area and per person, who owns them (brand shares and the
Herfindahl-Hirschman index), how near the nearest rival is, and what share of the people live near one.

    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with h3 python poi_compare.py POINTS.parquet REGIONS.parquet \
        OUT.csv [--population CELLS.parquet] [--within-m 500]

POINTS.parquet: lon, lat, and brand and operating_status when present (the output of poi_extract.py).
REGIONS.parquet: region_id, region_name, geometry (polygons, lon/lat). CELLS.parquet: h3 (an H3 index) and
population; a cell counts for the region that holds its centre, and its people are placed at its centre.

Per region: poi, area_km2, per_km2, population, poi_per_10k, branded_share, top_brand, top_brand_share, hhi
(each unbranded place counts as a firm of its own, so the index is not inflated by leaving them out),
unknown_status_share, median_m_to_other_brand (from each place to the nearest place of another brand or none; all
places of the study, so a rival across the border counts), pop_share_within_m (people within --within-m of any
place, by straight line, not by road). Every point is counted: in a region, or in none.
"""

import argparse
import csv
import json
import math
import sys

import numpy as np

R = 6371008.8


def local_metres(lon, lat, lat0):
    """Equirectangular metres around latitude lat0; fine within a city (error under 0.5 % across 50 km)."""
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    return np.radians(lon) * R * math.cos(math.radians(lat0)), np.radians(lat) * R


def hhi(brand_counts, unbranded):
    total = sum(brand_counts.values()) + unbranded
    if total == 0:
        return float("nan")
    return sum((v / total) ** 2 for v in brand_counts.values()) + unbranded * (1 / total) ** 2


def compare(points, regions, population=None, within_m=500.0):
    import duckdb
    from scipy.spatial import cKDTree
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    cols = {r[0] for r in c.execute(f"describe select * from read_parquet('{points}')").fetchall()}
    brand = "brand" if "brand" in cols else "null"
    status = "operating_status" if "operating_status" in cols else "'unknown'"
    c.execute(f"""create table p as select row_number() over () as k, lon, lat, {brand} as brand,
                  coalesce({status}, 'unknown') as status from read_parquet('{points}')""")
    c.execute(f"create table r as select region_id, region_name, geometry::geometry as geom from read_parquet('{regions}')")
    rows = c.execute("""select p.k, p.lon, p.lat, p.brand, p.status, r.region_id from p
                        left join r on st_contains(r.geom, st_point(p.lon, p.lat)) order by p.k""").fetchall()
    if len(rows) != c.execute("select count(*) from p").fetchall()[0][0]:
        raise SystemExit("a point fell in two regions: the regions overlap")
    areas = {}
    for rid, name, wkt, lat0 in c.execute("""select region_id, region_name, st_astext(geom), st_y(st_centroid(geom))
                                             from r""").fetchall():
        areas[rid] = {"name": name, "lat0": lat0}
        areas[rid]["km2"] = c.execute(f"""select st_area(st_transform(st_geomfromtext('{wkt}'), 'OGC:CRS84',
                       '+proj=laea +lat_0={lat0} +lon_0=0 +datum=WGS84', true))""").fetchall()[0][0] / 1e6
    lon = np.array([r[1] for r in rows])
    lat = np.array([r[2] for r in rows])
    lat0 = float(np.median(lat)) if len(lat) else 0.0
    x, y = local_metres(lon, lat, lat0)
    xy = np.c_[x, y]
    brands = np.array([r[3] if r[3] is not None else f"\0{r[0]}" for r in rows], dtype=object)
    tree = cKDTree(xy)
    to_other = np.full(len(rows), np.nan)
    for i in range(len(rows)):
        kk = min(len(rows), 16)
        while True:
            d, j = tree.query(xy[i], k=kk)
            d, j = np.atleast_1d(d), np.atleast_1d(j)
            ok = [dd for dd, jj in zip(d, j) if brands[jj] != brands[i]]
            if ok or kk >= len(rows):
                to_other[i] = ok[0] if ok else np.nan
                break
            kk = min(len(rows), kk * 4)
    pop, near = {}, {}
    if population:
        import h3
        cells = c.execute(f"select h3, population from read_parquet('{population}')").fetchall()
        cl = np.array([h3.cell_to_latlng(h)[0] for h, _ in cells])
        cn = np.array([h3.cell_to_latlng(h)[1] for h, _ in cells])
        c.execute("create table cc (lon double, lat double, population double)")
        c.executemany("insert into cc values (?, ?, ?)", [(float(a), float(b), float(v)) for a, b, (_, v) in zip(cn, cl, cells)])
        cx, cy = local_metres(cn, cl, lat0)
        d, _ = tree.query(np.c_[cx, cy], k=1) if len(rows) else (np.full(len(cells), np.inf), None)
        c.execute("create table cd (i integer, d double)")
        c.executemany("insert into cd values (?, ?)", [(i, float(v)) for i, v in enumerate(np.atleast_1d(d))])
        for rid, p, pn in c.execute(f"""
                with q as (select row_number() over () - 1 as i, lon, lat, population from cc)
                select r.region_id, sum(q.population), sum(q.population) filter (where cd.d <= {float(within_m)})
                from q join cd using (i) join r on st_contains(r.geom, st_point(q.lon, q.lat)) group by 1""").fetchall():
            pop[rid], near[rid] = p, pn or 0.0
    out = {}
    for rid, info in areas.items():
        idx = [i for i, r in enumerate(rows) if r[5] == rid]
        bc = {}
        for i in idx:
            if rows[i][3] is not None:
                bc[rows[i][3]] = bc.get(rows[i][3], 0) + 1
        n = len(idx)
        top = max(bc.items(), key=lambda kv: (kv[1], kv[0])) if bc else (None, 0)
        p = pop.get(rid)
        out[rid] = {
            "region_name": info["name"], "poi": n, "area_km2": info["km2"],
            "per_km2": n / info["km2"] if info["km2"] else float("nan"),
            "population": p, "poi_per_10k": (n / p * 1e4) if p else None,
            "branded_share": (sum(bc.values()) / n) if n else None,
            "top_brand": top[0], "top_brand_share": (top[1] / n) if n else None,
            "hhi": hhi(bc, n - sum(bc.values())) if n else None,
            "unknown_status_share": (sum(rows[i][4] == "unknown" for i in idx) / n) if n else None,
            "median_m_to_other_brand": float(np.nanmedian(to_other[idx])) if n and not np.all(np.isnan(to_other[idx])) else None,
            "pop_share_within_m": (near.get(rid, 0.0) / p) if p else None,
        }
    inside = sum(r[5] is not None for r in rows)
    return {"regions": out, "audit": {"points": len(rows), "in_a_region": inside, "in_no_region": len(rows) - inside}}


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("points")
    a.add_argument("regions")
    a.add_argument("out")
    a.add_argument("--population")
    a.add_argument("--within-m", type=float, default=500.0)
    a = a.parse_args(argv)
    res = compare(a.points, a.regions, a.population, a.within_m)
    keys = ["region_id"] + list(next(iter(res["regions"].values())).keys())
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(keys)
        for rid, v in sorted(res["regions"].items()):
            w.writerow([rid] + [("" if v[k] is None else (f"{v[k]:.6g}" if isinstance(v[k], float) else v[k]))
                                for k in keys[1:]])
    with open(a.out + ".audit.json", "w", encoding="utf-8") as f:
        json.dump({**res["audit"], "points_file": a.points, "regions_file": a.regions,
                   "population_file": a.population, "within_m": a.within_m}, f, indent=1)
    print(json.dumps(res["audit"]))


if __name__ == "__main__":
    sys.exit(main())

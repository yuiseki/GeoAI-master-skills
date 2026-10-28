"""Road, river and building features of one region from another source, in the same form as osm.npz, so the
static features can be rebuilt with one block swapped.

    road  ovt  Overture transportation/segment (subtype road); classes mapped as for OSM
          ksj  KSJ N13 (2024): major = road category national road, prefectural road or expressway (1, 2, 4);
               road = type ordinary (N13_002 = 1); track = type footpath or steps (3, 4), or width under 3 m (N13_006 = 1)
    river ovt  Overture base/water lines: river = class river or canal; stream = class stream
          ksj  KSJ W05 (2007-2009) river lines (the classes are read from the file; see the printout)
    bldg  ovt  Overture buildings (one centroid per building)

Distances are taken on the grid padded by 5 km, exactly as for OSM (grid_distance.py of the grid-risk-mapping skill).

Usage:
    ... python alt_features.py KIND SOURCE REGION ART_DIR SRC_DIR OUT.npz
"""

import glob
import json
import os
import sys
import zipfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.agents/skills/grid-risk-mapping/scripts"))
import grid_distance as gd  # noqa: E402

MAJOR = ["motorway", "trunk", "primary", "secondary", "tertiary"]
MINOR = ["unclassified", "residential", "living_street", "service"]
TRACK = ["track", "path", "footway", "bridleway"]
PAD = 50


def grid_of(art):
    m = json.load(open(f"{art}/grid.json"))
    return gd.GridSpec(m["x0"], m["y0"], m["nx"], m["ny"], m["size"]), m.get("crs", "EPSG:6678")


def to_grid_crs(geoms, src, dst):
    import pyproj
    import shapely

    tr = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    return shapely.transform(geoms, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))


def distances(g, groups):
    import shapely

    pg = gd.padded(g, PAD)
    out = {}
    for name, geoms in groups.items():
        geoms = shapely.get_parts(geoms)  # a multi-line can hold a part of one point
        ok = shapely.get_num_coordinates(geoms) >= 2
        if (~ok).any():
            print(f"  {name}: {int((~ok).sum())} line parts with fewer than two points left out")
        geoms = geoms[ok]
        pres = gd.line_presence(pg, geoms)
        out[f"d_{name}"] = gd.crop(gd.distance_m(pres, g.size), PAD, g).astype(np.float32)
        print(f"  {name}: {len(geoms)} lines, cells marked {int(gd.crop(pres, PAD, g).sum())}")
    return out


def lines_only(geoms):
    import shapely

    t = shapely.get_type_id(geoms)
    return np.isin(t, [1, 5])  # LineString, MultiLineString


def main():
    import duckdb
    import shapely

    kind, source, region, art, src_dir, out = sys.argv[1:7]
    g, crs = grid_of(art)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    if kind == "road" and source == "ovt":
        df = con.execute(f"SELECT class, wkb FROM '{src_dir}/{region}_segment.parquet' WHERE subtype = 'road'").df()
        geoms = to_grid_crs(shapely.from_wkb(df.wkb.map(bytes).to_numpy()), "EPSG:4326", crs)
        c = df["class"].to_numpy()
        res = distances(g, {"road_major": geoms[np.isin(c, MAJOR)], "road": geoms[np.isin(c, MAJOR + MINOR)], "track": geoms[np.isin(c, TRACK)]})
    elif kind == "road" and source == "ksj":
        parts = []
        for z in sorted(glob.glob(f"{src_dir}/N13-24_*_SHP.zip")):
            shp = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith(".shp"))
            parts.append(con.execute(f"""SELECT N13_002 t, N13_003 c, N13_006 w, ST_AsWKB(geom) wkb FROM ST_Read('/vsizip/{z}/{shp}')
                                         WHERE ST_Intersects(geom, ST_MakeEnvelope({{box}}))""".replace("{box}", ",".join(map(str, lonlat_box(g, crs))))).df())
        df = __import__("pandas").concat(parts, ignore_index=True)
        geoms = to_grid_crs(shapely.from_wkb(df.wkb.map(bytes).to_numpy()), "EPSG:6668", crs)
        t, cc, w = df.t.to_numpy(), df.c.to_numpy(), df.w.to_numpy()
        res = distances(g, {"road_major": geoms[np.isin(cc, ["1", "2", "4"])], "road": geoms[t == "1"],
                            "track": geoms[np.isin(t, ["3", "4"]) | ((t == "1") & (w == "1"))]})
    elif kind == "river" and source == "ovt":
        df = con.execute(f"SELECT class, wkb FROM '{src_dir}/{region}_water.parquet'").df()
        geoms = shapely.from_wkb(df.wkb.map(bytes).to_numpy())
        keep = lines_only(geoms)
        print(f"  water rows {len(df)}, lines {int(keep.sum())}; classes of lines:", df[keep]["class"].value_counts().head(8).to_dict())
        geoms, c = to_grid_crs(geoms[keep], "EPSG:4326", crs), df["class"].to_numpy()[keep]
        res = distances(g, {"river": geoms[np.isin(c, ["river", "canal"])], "stream": geoms[c == "stream"]})
    elif kind == "river" and source == "ksj":
        res = ksj_rivers(con, g, crs, src_dir, region)
    elif kind == "bldg" and source == "ovt":
        df = con.execute(f"SELECT lon, lat, source FROM '{src_dir}/{region}_building.parquet'").df()
        import pyproj

        x, y = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(df.lon.to_numpy(), df.lat.to_numpy())
        pg = gd.padded(g, PAD)
        cnt, off = gd.point_counts(pg, x, y)
        print(f"  buildings {len(df)} (sources {df.source.value_counts().to_dict()}); off the padded grid {off}")
        res = {"n_building": gd.crop(cnt, PAD, g).astype(np.float32), "d_building": gd.crop(gd.distance_m(cnt > 0, g.size), PAD, g).astype(np.float32)}
    else:
        raise SystemExit(f"unknown {kind} {source}")
    np.savez_compressed(out, **res)
    print("wrote", out, list(res))


def lonlat_box(g, crs, margin=0.06):
    import pyproj

    tr = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    xs = [g.x0, g.x0 + g.nx * g.size]
    ys = [g.y0, g.y0 + g.ny * g.size]
    lon, lat = tr.transform([xs[0], xs[0], xs[1], xs[1]], [ys[0], ys[1], ys[0], ys[1]])
    return (min(lon) - margin, min(lat) - margin, max(lon) + margin, max(lat) + margin)


W05_PREF = {"akita": "05", "gifu": "21", "kyoto": "26", "ishikawa": "17"}
RIVER_SECTIONS = ["1", "2", "3", "5", "6", "7"]  # class A (national, prefectural), class B, also those doubling as lakes
STREAM_SECTIONS = ["0", "4", "8"]  # outside the designated sections, or unknown


def ksj_rivers(con, g, crs, src_dir, region):
    import pandas as pd
    import shapely

    z = glob.glob(f"{src_dir}/W05-*_{W05_PREF[region]}_GML.zip")[0]
    shp = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith("_Stream.shp"))
    # only the code columns: the river names are Shift-JIS and are not needed
    df = con.execute(f"SELECT W05_003 sec, ST_AsWKB(geom) wkb FROM ST_Read('/vsizip/{z}/{shp}')").df()
    print(f"  W05 {os.path.basename(z)}: {len(df)} lines; section codes {df.sec.value_counts().to_dict()}")
    geoms = to_grid_crs(shapely.from_wkb(df.wkb.map(bytes).to_numpy()), "EPSG:4612", crs)
    sec = df.sec.to_numpy()
    return distances(g, {"river": geoms[np.isin(sec, RIVER_SECTIONS)], "stream": geoms[np.isin(sec, STREAM_SECTIONS)]})


if __name__ == "__main__":
    main()

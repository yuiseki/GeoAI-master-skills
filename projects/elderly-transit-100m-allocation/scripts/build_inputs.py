"""Build fixed-version inputs and 1 km mesh units for the 100 m allocation study.

Run from repository root with the analysis venv:
  /tmp/venv-geoai/bin/python projects/elderly-transit-100m-allocation/scripts/build_inputs.py
"""

import json
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.name
OUTPUT = PROJECT / "outputs"

ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
CENSUS_REV = "6c486c8649484e09e549c0c99b5fa89b4f416edb"
BUS_REV = "442223b4544103a922f21081c070dd5c69e4c23e"
STATION_REV = "a33321099406b47338be0d03a4887059473fde0c"
OSM_REV = "9a9b4a77e89e28a66bf15781644a16b63501f622"

ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
CENSUS = f"hf://datasets/yuiseki/estat-census-mesh-2020@{CENSUS_REV}/parquet/T001140.parquet"
BUS_BASE = f"hf://datasets/yuiseki/ksj-p11-bus-stop-jp@{BUS_REV}/parquet/prefectures"
STATION = f"hf://datasets/yuiseki/ekidata-jp@{STATION_REV}/parquet/2026-10-05/station.2026-07-31.parquet"
OSM = f"hf://datasets/yuiseki/osm-japan-src-2026-08@{OSM_REV}/parquet/planet_osm_line.parquet"


def one(con, sql):
    return con.execute(sql).fetchone()


def mesh_bounds(code):
    if len(code) != 8 or not code.isdigit():
        raise ValueError(f"invalid third-level mesh code {code}")
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def aggregate_census(rows):
    result = {}
    for code, pref, total, age65, age75, secrecy in rows:
        if pref != "13":
            continue
        if code in result:
            raise ValueError(f"duplicate Tokyo census mesh {code}")
        if len(code) != 8 or not code.isdigit():
            raise ValueError(f"invalid census mesh {code}")
        n = int(total)
        if n < 0:
            raise ValueError("negative population")
        a65 = int(age65) if secrecy == "0" and age65 not in (None, "*") else None
        a75 = int(age75) if secrecy == "0" and age75 not in (None, "*") else None
        if ((a65 is not None and not 0 <= a65 <= n)
                or (a75 is not None and not 0 <= a75 <= n)
                or (a65 is not None and a75 is not None and a75 > a65)):
            raise ValueError(f"inconsistent age counts {code}")
        result[code] = {"total": n, "age65": a65, "age75": a75, "secrecy": secrecy}
    return result


def cached(con, path, query):
    if not path.exists():
        con.execute(f"copy ({query}) to '{path}' (format parquet)")
    return path


def main():
    import shapely
    from pyproj import Transformer
    from shapely.prepared import prep

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("set memory_limit='20GB'; set threads=8")
    con.execute("install spatial; load spatial; install httpfs; load httpfs")

    admin_file = cached(
        con,
        ARTIFACTS / "mainland-municipalities.parquet",
        f"""select code5, name, geometry from '{ADMIN}'
            where pref_code='13' and (code5 between '13101' and '13123'
              or code5 like '132%' or code5 in ('13303','13305','13307','13308'))""",
    )
    con.execute(f"create view municipalities as select * from '{admin_file}'")
    municipality_count = one(con, "select count(*) from municipalities")[0]
    if municipality_count != 53:
        raise ValueError(f"expected 53 mainland municipalities, got {municipality_count}")
    mainland_wkb = one(con, "select ST_AsWKB(ST_Union_Agg(geometry)) from municipalities")[0]
    mainland = prep(shapely.from_wkb(bytes(mainland_wkb)))
    xmin, ymin, xmax, ymax = one(
        con,
        """select ST_XMin(g),ST_YMin(g),ST_XMax(g),ST_YMax(g) from
           (select ST_Transform(ST_Union_Agg(geometry), 'EPSG:4612', 'EPSG:3857',
             always_xy := true) g from municipalities)""",
    )
    pad = 15000
    xmin, ymin, xmax, ymax = xmin - pad, ymin - pad, xmax + pad, ymax + pad
    to_geographic = Transformer.from_crs(3857, 4326, always_xy=True)
    lon_min, lat_min = to_geographic.transform(xmin, ymin)
    lon_max, lat_max = to_geographic.transform(xmax, ymax)

    census_file = cached(
        con,
        ARTIFACTS / "tokyo-census-age.parquet",
        f"""select prefecture, KEY_CODE, HTKSYORI, T001140001, T001140019, T001140022
            from '{CENSUS}' where prefecture='13'""",
    )
    census_raw = con.execute(
        f"""select KEY_CODE,prefecture,T001140001,T001140019,T001140022,HTKSYORI
            from '{census_file}'"""
    ).fetchall()
    census = aggregate_census(census_raw)

    mesh_rows = []
    quarter_positions = {}
    for code, data in census.items():
        west, south, east, north = mesh_bounds(code)
        lon, lat = (west + east) / 2, (south + north) / 2
        if not mainland.covers(shapely.Point(lon, lat)):
            continue
        mesh_rows.append({"mesh": code, "lon": lon, "lat": lat, **data})
        quarter_positions[code] = [
            (west + (east - west) * fx, south + (north - south) * fy)
            for fx, fy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
            if mainland.covers(shapely.Point(west + (east - west) * fx, south + (north - south) * fy))
        ]
    mesh_rows.sort(key=lambda row: row["mesh"])

    con.execute("create temp table centers (mesh varchar, lon double, lat double)")
    con.executemany(
        "insert into centers values (?,?,?)",
        [(r["mesh"], r["lon"], r["lat"]) for r in mesh_rows],
    )
    matches = con.execute(
        """select c.mesh, min(m.code5), min(m.name), count(m.code5)
           from centers c left join municipalities m
             on ST_Intersects(m.geometry, ST_SetCRS(ST_Point(c.lon,c.lat), 'EPSG:4612'))
           group by c.mesh"""
    ).fetchall()
    if any(n == 0 for _, _, _, n in matches):
        raise ValueError("mesh center selected by union but not by any municipality")
    by_mesh = {code: (municipality, name) for code, municipality, name, _ in matches}
    for row in mesh_rows:
        row["municipality_code"], row["municipality"] = by_mesh[row["mesh"]]

    bus_files = ",".join(f"'{BUS_BASE}/{p}.parquet'" for p in (11, 12, 13, 14, 19))
    bus_file = cached(
        con,
        ARTIFACTS / "bus-buffer.parquet",
        f"""select id,name,operator,ST_X(geometry) as lon,ST_Y(geometry) as lat
            from read_parquet([{bus_files}])
            where ST_X(geometry) between {lon_min} and {lon_max}
              and ST_Y(geometry) between {lat_min} and {lat_max}""",
    )
    bus_rows = con.execute(f"select id,name,operator,lon,lat from '{bus_file}'").fetchall()
    if len(bus_rows) != len({row[0] for row in bus_rows}):
        raise ValueError("duplicate bus ID")
    bus_by_coord = {}
    for stop_id, name, operator, lon, lat in bus_rows:
        key = (round(lon, 7), round(lat, 7))
        bus_by_coord.setdefault(key, (stop_id, name, operator, lon, lat))

    station_file = cached(
        con,
        ARTIFACTS / "stations-buffer.parquet",
        f"""select station_cd,station_g_cd,station_name,lon,lat,e_status from '{STATION}'
            where lon between {lon_min} and {lon_max} and lat between {lat_min} and {lat_max}""",
    )
    station_rows = con.execute(
        f"select station_cd,station_g_cd,station_name,lon,lat,e_status from '{station_file}'"
    ).fetchall()
    if len({row[0] for row in station_rows}) != len(station_rows):
        raise ValueError("duplicate station_cd")
    active_stations = [row for row in station_rows if row[5] == 0]
    if not active_stations:
        raise ValueError("no active stations in buffer")

    road_file = cached(
        con,
        ARTIFACTS / "osm-lines-buffer.parquet",
        f"""select osm_id,highway,foot,access,way from '{OSM}'
            where bbox.xmin <= {xmax} and bbox.xmax >= {xmin}
              and bbox.ymin <= {ymax} and bbox.ymax >= {ymin}
              and highway is not null""",
    )
    road_valid = one(
        con,
        f"select count(*) filter (where way is null or not ST_IsValid(way)) from '{road_file}'",
    )[0]
    if road_valid:
        raise ValueError(f"{road_valid} invalid road geometries")

    con.execute("create temp table mesh_table (mesh varchar, lon double, lat double, total bigint, age65 bigint, age75 bigint, secrecy varchar, municipality_code varchar, municipality varchar)")
    con.executemany(
        "insert into mesh_table values (?,?,?,?,?,?,?,?,?)",
        [
            (r["mesh"], r["lon"], r["lat"], r["total"], r["age65"], r["age75"],
             r["secrecy"], r["municipality_code"], r["municipality"])
            for r in mesh_rows
        ],
    )
    con.execute(f"copy mesh_table to '{ARTIFACTS / 'meshes.parquet'}' (format parquet)")
    con.execute("create temp table quarter_table (mesh varchar, lon double, lat double)")
    con.executemany(
        "insert into quarter_table values (?,?,?)",
        [(code, lon, lat) for code, points in quarter_positions.items() for lon, lat in points],
    )
    con.execute(f"copy quarter_table to '{ARTIFACTS / 'quarter-points.parquet'}' (format parquet)")

    accounting = {
        "made": date.today().isoformat(),
        "sources": {
            "census": CENSUS,
            "bus": [f"{BUS_BASE}/{p}.parquet" for p in (11, 12, 13, 14, 19)],
            "station": STATION,
            "osm": OSM,
            "admin": ADMIN,
        },
        "mainland_municipalities": municipality_count,
        "tokyo_census_rows": len(census_raw),
        "center_inside_mainland_meshes": len(mesh_rows),
        "suppressed_age_meshes": sum(row["age65"] is None for row in mesh_rows),
        "bus_rows_buffer": len(bus_rows),
        "bus_unique_coordinates": len(bus_by_coord),
        "bus_duplicates_by_coordinate": len(bus_rows) - len(bus_by_coord),
        "station_rows_buffer": len(station_rows),
        "station_active_rows": len(active_stations),
        "station_active_groups": len({row[1] for row in active_stations}),
        "osm_bbox_highway_rows": one(con, f"select count(*) from '{road_file}'")[0],
        "quarter_points": sum(len(v) for v in quarter_positions.values()),
        "bbox_epsg3857_padded": [xmin, ymin, xmax, ymax],
        "bbox_epsg4326_padded": [lon_min, lat_min, lon_max, lat_max],
        "crs": {
            "census_mesh": "JGD2011 third-level mesh",
            "bus": "EPSG:6668",
            "station": "OGC:CRS84",
            "osm": "EPSG:3857",
            "admin": "EPSG:4612",
            "length": "EPSG:6677",
        },
    }
    (OUTPUT / "input-accounting.json").write_text(
        json.dumps(accounting, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(accounting, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

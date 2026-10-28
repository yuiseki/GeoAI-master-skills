"""Task 39: older residents far from both a bus stop and an active station.

Run from repository root:
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy \
  --with shapely --with pyproj python \
  projects/_transit/tokyo-mainland-elderly-transit-gaps/scripts/analyze.py
"""

import csv
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.parent.name / PROJECT.name
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
WALK_CLASSES = {
    "residential", "living_street", "service", "unclassified", "tertiary",
    "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
    "footway", "pedestrian", "path", "track", "steps",
}


def mesh_bounds(code):
    if len(code) != 8 or not code.isdigit():
        raise ValueError(f"invalid third-level mesh code {code}")
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def aggregate_census(rows):
    """Only Tokyo's part of a border mesh; keep suppressed ages unknown."""
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


def walkable(highway, foot, access, *, include_steps=False):
    if highway not in WALK_CLASSES or (highway == "steps" and not include_steps):
        return False
    if foot in ("no", "private") or access in ("no", "private"):
        return False
    return True


def build_graph(lines):
    """Undirected metric graph from all vertices of projected OSM line strings."""
    import numpy as np
    from scipy.sparse import csr_matrix

    node_ids = {}
    positions = []
    edges = {}
    line_count = 0
    for line in lines:
        line_count += 1
        if len(line) < 2:
            continue
        ids = []
        for x, y in line:
            key = (round(float(x), 2), round(float(y), 2))
            if key not in node_ids:
                node_ids[key] = len(positions)
                positions.append(key)
            ids.append(node_ids[key])
        for a, b, p, q in zip(ids[:-1], ids[1:], line[:-1], line[1:]):
            length = math.hypot(q[0] - p[0], q[1] - p[1])
            if a == b or length <= 0:
                continue
            key = (min(a, b), max(a, b))
            if key not in edges or length < edges[key]:
                edges[key] = length
    if not edges:
        raise ValueError("no traversable road edges")
    u = np.fromiter((a for a, _ in edges), dtype=np.int32)
    v = np.fromiter((b for _, b in edges), dtype=np.int32)
    w = np.fromiter(edges.values(), dtype=float)
    graph = csr_matrix((np.r_[w, w], (np.r_[u, v], np.r_[v, u])), shape=(len(positions), len(positions)))
    return graph, np.asarray(positions, dtype=float), {"lines": line_count, "nodes": len(positions), "edges": len(edges), "length_km": float(w.sum() / 1000)}


def snap_points(positions, coordinates, *, max_snap_m, tree=None):
    from scipy.spatial import cKDTree

    if tree is None:
        tree = cKDTree(coordinates)
    if not positions:
        return []
    d, ids = tree.query(positions)
    return [(int(i), float(m)) if m <= max_snap_m else (None, float(m)) for i, m in zip(ids, d)]


def multi_source_distances(graph, coordinates, destinations, *, max_snap_m=200, tree=None):
    import numpy as np
    from scipy.sparse import coo_matrix, vstack, hstack
    from scipy.sparse.csgraph import dijkstra

    snapped = snap_points(destinations, coordinates, max_snap_m=max_snap_m, tree=tree)
    sources = {}
    for node, offset in snapped:
        if node is not None:
            sources[node] = min(offset, sources.get(node, math.inf))
    if not sources:
        return np.full(graph.shape[0], math.inf)
    n = graph.shape[0]
    top = coo_matrix((list(sources.values()), ([0] * len(sources), list(sources))), shape=(1, n)).tocsr()
    # A strictly positive connector avoids sparse matrices silently dropping 0 edges.
    top.data = np.maximum(top.data, 1e-6)
    augmented = vstack([hstack([graph, top.T]), hstack([top, coo_matrix((1, 1))])]).tocsr()
    return dijkstra(augmented, directed=False, indices=n)[:n]


def distance_from_point(point, coordinates, node_distances, *, max_snap_m=500, tree=None):
    snap = snap_points([point], coordinates, max_snap_m=max_snap_m, tree=tree)[0]
    node, offset = snap
    if node is None or not math.isfinite(node_distances[node]):
        return None
    return float(node_distances[node] + offset)


def rank_gaps(rows, *, bus_threshold, rail_threshold, age_key="age65"):
    selected = [row for row in rows if row.get(age_key) is not None and row.get("bus_m") is not None
                and row.get("rail_m") is not None and row["bus_m"] > bus_threshold
                and row["rail_m"] > rail_threshold]
    return sorted(selected, key=lambda row: (-row[age_key], -row["bus_m"], row["mesh"]))


def sample_gap_fraction(points, bus_threshold, rail_threshold):
    """Equal-location sensitivity; a disconnected sample makes the cell unknown."""
    if not points or any(bus is None or rail is None for bus, rail in points):
        return None
    return sum(bus > bus_threshold and rail > rail_threshold for bus, rail in points) / len(points)


def cached(con, path, query):
    if not path.exists():
        con.sql(f"copy ({query}) to '{path}' (format parquet)")
    return path


def write_csv(rows, path):
    if not rows:
        raise ValueError("no rows to write")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    import duckdb
    import numpy as np
    import shapely
    from pyproj import Transformer
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    from shapely.prepared import prep

    ARTIFACTS.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.sql("set memory_limit='6GB'; set threads=4; install spatial; load spatial; install httpfs; load httpfs")
    admin_file = cached(con, ARTIFACTS / "mainland-municipalities.parquet", f"select code5, name, geometry from '{ADMIN}' where pref_code='13' and (code5 between '13101' and '13123' or code5 like '132%' or code5 in ('13303','13305','13307','13308'))")
    con.sql(f"create view municipalities as select * from '{admin_file}'")
    municipality_count = con.sql("select count(*) from municipalities").fetchone()[0]
    if municipality_count != 53:
        raise ValueError(f"expected 53 mainland municipalities, got {municipality_count}")
    mainland_wkb = con.sql("select ST_AsWKB(ST_Union_Agg(geometry)) from municipalities").fetchone()[0]
    mainland = prep(shapely.from_wkb(bytes(mainland_wkb)))
    xmin, ymin, xmax, ymax = con.sql("""
        select ST_XMin(g),ST_YMin(g),ST_XMax(g),ST_YMax(g) from
        (select ST_Transform(ST_Union_Agg(geometry), 'EPSG:4612', 'EPSG:3857', always_xy := true) g from municipalities)
    """).fetchone()
    pad = 15000
    xmin, ymin, xmax, ymax = xmin-pad, ymin-pad, xmax+pad, ymax+pad
    to_geographic = Transformer.from_crs(3857, 4326, always_xy=True)
    lon_min, lat_min = to_geographic.transform(xmin, ymin)
    lon_max, lat_max = to_geographic.transform(xmax, ymax)
    to_metric = Transformer.from_crs(4326, 6677, always_xy=True)

    census_file = cached(con, ARTIFACTS / "tokyo-census-age.parquet", f"select prefecture, KEY_CODE, HTKSYORI, T001140001, T001140019, T001140022 from '{CENSUS}' where prefecture='13'")
    census_raw = con.sql(f"select KEY_CODE,prefecture,T001140001,T001140019,T001140022,HTKSYORI from '{census_file}'").fetchall()
    census = aggregate_census(census_raw)
    mesh_rows = []
    quarter_positions = {}
    for code, data in census.items():
        west, south, east, north = mesh_bounds(code)
        lon, lat = (west+east)/2, (south+north)/2
        if not mainland.covers(shapely.Point(lon, lat)):
            continue
        mesh_rows.append({"mesh": code, "lon": lon, "lat": lat, **data})
        quarter_positions[code] = [(west+(east-west)*fx, south+(north-south)*fy)
                                   for fx, fy in ((0.25,0.25),(0.75,0.25),(0.25,0.75),(0.75,0.75))
                                   if mainland.covers(shapely.Point(west+(east-west)*fx,south+(north-south)*fy))]
    mesh_rows.sort(key=lambda row: row["mesh"])
    # A centroid can fall into a different municipality than a small part of the mesh.
    con.sql("create temp table centers (mesh varchar, lon double, lat double)")
    con.executemany("insert into centers values (?,?,?)", [(r["mesh"],r["lon"],r["lat"]) for r in mesh_rows])
    matches = con.sql("""
        select c.mesh, min(m.code5), min(m.name), count(m.code5) from centers c
        left join municipalities m on ST_Intersects(m.geometry,
          ST_SetCRS(ST_Point(c.lon,c.lat), 'EPSG:4612')) group by c.mesh
    """).fetchall()
    by_mesh = {code:(municipality,name,n) for code,municipality,name,n in matches}
    if any(n == 0 for _,_,_,n in matches):
        raise ValueError("mesh center selected by union but not by any municipality")
    for row in mesh_rows:
        row["municipality_code"], row["municipality"], _ = by_mesh[row["mesh"]]

    bus_files = ",".join(f"'{BUS_BASE}/{p}.parquet'" for p in (11,12,13,14,19))
    bus_file = cached(con, ARTIFACTS / "bus-buffer.parquet", f"select id,name,operator,ST_X(geometry) as lon,ST_Y(geometry) as lat from read_parquet([{bus_files}]) where ST_X(geometry) between {lon_min} and {lon_max} and ST_Y(geometry) between {lat_min} and {lat_max}")
    bus_rows = con.sql(f"select id,name,operator,lon,lat from '{bus_file}'").fetchall()
    if len(bus_rows) != len({row[0] for row in bus_rows}):
        raise ValueError("duplicate bus ID")
    bus_by_coord = {}
    for stop_id, name, operator, lon, lat in bus_rows:
        key = (round(lon, 7), round(lat, 7))
        bus_by_coord.setdefault(key, (stop_id, name, operator, lon, lat))
    station_file = cached(con, ARTIFACTS / "stations-buffer.parquet", f"select station_cd,station_g_cd,station_name,lon,lat,e_status from '{STATION}' where lon between {lon_min} and {lon_max} and lat between {lat_min} and {lat_max}")
    station_rows = con.sql(f"select station_cd,station_g_cd,station_name,lon,lat,e_status from '{station_file}'").fetchall()
    active_stations = [row for row in station_rows if row[5] == 0]
    if len({row[0] for row in station_rows}) != len(station_rows):
        raise ValueError("duplicate station_cd")
    road_file = cached(con, ARTIFACTS / "osm-lines-buffer.parquet", f"select osm_id,highway,foot,access,way from '{OSM}' where bbox.xmin <= {xmax} and bbox.xmax >= {xmin} and bbox.ymin <= {ymax} and bbox.ymax >= {ymin} and highway is not null")
    con.sql(f"create view osm_lines as select * from '{road_file}'")
    road_rows_count = con.sql("select count(*) from osm_lines").fetchone()[0]
    road_valid = con.sql("select count(*) filter (where way is null or not ST_IsValid(way)) from osm_lines").fetchone()[0]
    if road_valid:
        raise ValueError(f"{road_valid} invalid road geometries")

    def walk_lines(include_steps=False):
        selected = 0
        cursor = con.execute("select highway,foot,access,ST_AsWKB(ST_Transform(way,'EPSG:3857','EPSG:6677',always_xy := true)) from osm_lines")
        while chunk := cursor.fetchmany(5000):
            for highway, foot, access, wkb in chunk:
                if not walkable(highway, foot, access, include_steps=include_steps):
                    continue
                selected += 1
                geom = shapely.from_wkb(bytes(wkb))
                for part in getattr(geom, "geoms", [geom]):
                    if part.geom_type == "LineString":
                        yield list(part.coords)

    graph, coordinates, graph_info = build_graph(walk_lines())
    components, labels = connected_components(graph, directed=False)
    component_sizes = np.bincount(labels)
    tree = cKDTree(coordinates)
    bus_positions = [to_metric.transform(lon,lat) for *_,lon,lat in bus_by_coord.values()]
    station_positions = [to_metric.transform(row[3],row[4]) for row in active_stations]
    bus_snaps = snap_points(bus_positions, coordinates, max_snap_m=200, tree=tree)
    rail_snaps = snap_points(station_positions, coordinates, max_snap_m=200, tree=tree)
    bus_d = multi_source_distances(graph, coordinates, bus_positions, tree=tree)
    rail_d = multi_source_distances(graph, coordinates, station_positions, tree=tree)
    center_positions = [to_metric.transform(row["lon"],row["lat"]) for row in mesh_rows]
    center_snaps = snap_points(center_positions, coordinates, max_snap_m=500, tree=tree)
    bus_tree = cKDTree(bus_positions)
    rail_tree = cKDTree(station_positions)
    bus_euclidean, _ = bus_tree.query(center_positions)
    rail_euclidean, _ = rail_tree.query(center_positions)
    for row, point, snap, bus_straight, rail_straight in zip(mesh_rows,center_positions,center_snaps,bus_euclidean,rail_euclidean):
        node, offset = snap
        row["snap_m"] = offset
        row["component"] = int(labels[node]) if node is not None else None
        row["bus_m"] = float(bus_d[node] + offset) if node is not None and math.isfinite(bus_d[node]) else None
        row["rail_m"] = float(rail_d[node] + offset) if node is not None and math.isfinite(rail_d[node]) else None
        row["bus_straight_m"] = float(bus_straight)
        row["rail_straight_m"] = float(rail_straight)
        row["age65_share"] = row["age65"] / row["total"] if row["age65"] is not None and row["total"] else None

    ranked = rank_gaps(mesh_rows, bus_threshold=800, rail_threshold=1500)
    straight_rows = [row | {"bus_m":row["bus_straight_m"],"rail_m":row["rail_straight_m"]} for row in mesh_rows]
    straight_ranked = rank_gaps(straight_rows, bus_threshold=800, rail_threshold=1500)
    sensitivity = {}
    for bus_limit, rail_limit in ((500,1000),(1000,2000)):
        r = rank_gaps(mesh_rows, bus_threshold=bus_limit, rail_threshold=rail_limit)
        sensitivity[f"bus{bus_limit}_rail{rail_limit}"] = {"candidate_meshes":len(r),"top10":[x["mesh"] for x in r[:10]]}
    age75_ranked = rank_gaps(mesh_rows, bus_threshold=800, rail_threshold=1500, age_key="age75")
    # Five evenly weighted representative points are sensitivity, not a population allocation.
    quarter_points = [to_metric.transform(lon,lat) for row in mesh_rows for lon,lat in quarter_positions[row["mesh"]]]
    quarter_snaps = snap_points(quarter_points, coordinates, max_snap_m=500, tree=tree)
    cursor = 0
    five_rows = []
    for row in mesh_rows:
        points = [(row["bus_m"], row["rail_m"])]
        for snap in quarter_snaps[cursor:cursor+len(quarter_positions[row["mesh"]])]:
            node, offset = snap
            points.append((float(bus_d[node]+offset) if node is not None and math.isfinite(bus_d[node]) else None,
                           float(rail_d[node]+offset) if node is not None and math.isfinite(rail_d[node]) else None))
        cursor += len(quarter_positions[row["mesh"]])
        share = sample_gap_fraction(points, 800, 1500)
        five_rows.append(row | {"sample_points":len(points),"sample_valid":sum(bus is not None and rail is not None for bus,rail in points),
                                "sample_gap_fraction":share,
                                "sample_gap_age65":row["age65"]*share if share is not None and row["age65"] is not None else None})
    five_ranked = sorted([r for r in five_rows if r["sample_gap_age65"] is not None and r["sample_gap_fraction"] > 0],
                         key=lambda row:(-row["sample_gap_age65"],row["mesh"]))
    primary_codes = {row["mesh"] for row in ranked[:10]}
    accounting = {
        "mainland_municipalities": municipality_count,
        "tokyo_census_rows":len(census_raw),
        "center_inside_mainland_meshes":len(mesh_rows),
        "suppressed_age_meshes":sum(row["age65"] is None for row in mesh_rows),
        "bus_rows_buffer":len(bus_rows),
        "bus_unique_coordinates":len(bus_by_coord),
        "bus_duplicates_by_coordinate":len(bus_rows)-len(bus_by_coord),
        "bus_snapped_within_200m":sum(node is not None for node,_ in bus_snaps),
        "station_rows_buffer":len(station_rows),
        "station_active_rows":len(active_stations),
        "station_active_groups":len({row[1] for row in active_stations}),
        "station_snapped_within_200m":sum(node is not None for node,_ in rail_snaps),
        "osm_bbox_highway_rows":road_rows_count,
        "walk_graph":graph_info | {"components":int(components),"largest_component_nodes":int(component_sizes.max()),"largest_component_share":float(component_sizes.max()/len(coordinates))},
        "mesh_snap_within_500m":sum(node is not None for node,_ in center_snaps),
        "mesh_bus_reachable":sum(row["bus_m"] is not None for row in mesh_rows),
        "mesh_rail_reachable":sum(row["rail_m"] is not None for row in mesh_rows),
        "mesh_both_reachable_with_age":sum(row["bus_m"] is not None and row["rail_m"] is not None and row["age65"] is not None for row in mesh_rows),
        "primary_gap_meshes":len(ranked),
        "primary_gap_age65_sum":sum(row["age65"] for row in ranked),
        "straight_gap_meshes":len(straight_ranked),
        "quarter_sample_points":len(quarter_points),
        "quarter_valid_gap_meshes":len(five_ranked),
    }
    gap_codes = {row["mesh"] for row in ranked}
    sample_by_code = {row["mesh"]:row for row in five_rows}
    output_rows = [{k:v for k,v in row.items() if k not in ("secrecy","component")}
                   | {"age65_gap_priority":row["age65"] if row["mesh"] in gap_codes else 0 if row["age65"] is not None and row["bus_m"] is not None and row["rail_m"] is not None else None,
                      "sample_gap_fraction":sample_by_code[row["mesh"]]["sample_gap_fraction"],
                      "sample_gap_age65":sample_by_code[row["mesh"]]["sample_gap_age65"],
                      "sample_points":sample_by_code[row["mesh"]]["sample_points"],
                      "sample_valid":sample_by_code[row["mesh"]]["sample_valid"]}
                   for row in mesh_rows]
    write_csv(output_rows, OUTPUT / "mesh-results.csv")
    result = {
        "question":"東京都本土で65歳以上が多く駅とバス停の両方から歩いて遠い3次メッシュ",
        "made":date.today().isoformat(),
        "sources":{"census":CENSUS,"bus":[f"{BUS_BASE}/{p}.parquet" for p in (11,12,13,14,19)],"station":STATION,"osm":OSM,"admin":ADMIN},
        "thresholds_m":{"bus":800,"rail":1500,"mesh_snap":500,"destination_snap":200},
        "crs":{"census_mesh":"JGD2011 third-level mesh","bus":"EPSG:6668","station":"OGC:CRS84","osm":"EPSG:3857","admin":"EPSG:4612","length":"EPSG:6677"},
        "accounting":accounting,
        "top10":ranked[:10],
        "top10_straight":[row["mesh"] for row in straight_ranked[:10]],
        "top10_age75":[row["mesh"] for row in age75_ranked[:10]],
        "top10_five_points":[row["mesh"] for row in five_ranked[:10]],
        "top10_five_points_detail":[{"mesh":row["mesh"],"municipality":row["municipality"],"age65":row["age65"],"sample_gap_fraction":row["sample_gap_fraction"],"sample_gap_age65":row["sample_gap_age65"],"sample_points":row["sample_points"],"sample_valid":row["sample_valid"]} for row in five_ranked[:10]],
        "top10_overlap":{"straight":len(primary_codes & {row["mesh"] for row in straight_ranked[:10]}),
                         "age75":len(primary_codes & {row["mesh"] for row in age75_ranked[:10]}),
                         "five_points":len(primary_codes & {row["mesh"] for row in five_ranked[:10]})},
        "sensitivity":sensitivity,
    }
    (OUTPUT / "analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    con.sql("create temp table map_rows (mesh varchar, age65_gap_priority double, age65 double, age65_share double, bus_m double, rail_m double, wkt varchar)")
    map_data = []
    for row in output_rows:
        west,south,east,north = mesh_bounds(row["mesh"])
        polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        map_data.append((row["mesh"],row["age65_gap_priority"],row["age65"],row["age65_share"],row["bus_m"],row["rail_m"],polygon))
    con.executemany("insert into map_rows values (?,?,?,?,?,?,?)", map_data)
    con.sql(f"copy (select mesh,age65_gap_priority,age65,age65_share,bus_m,rail_m,ST_GeomFromText(wkt) as geometry from map_rows) to '{ARTIFACTS / 'map-units.parquet'}' (format parquet)")
    print(json.dumps({"accounting":accounting,"top10":ranked[:10],"top10_overlap":result["top10_overlap"],"sensitivity":sensitivity},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()

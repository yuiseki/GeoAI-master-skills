"""Cut the frozen inputs for Taito-ku plus a buffer, and count what came in.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with pyarrow python scripts/01_fetch.py [--buffer-m 5000]

Writes to artifacts/_evacuation_shelter/taito-bridge-cut-detour/raw_b<buffer>/:
  taito.parquet     Taito-ku (code5 13106) polygon, EPSG:6677
  area.parquet      the polygon buffered by --buffer-m, EPSG:6677
  lines.parquet     OSM lines with highway, railway or waterway inside the buffer, EPSG:6677
  water.parquet     OSM water polygons (natural=water, waterway=riverbank) inside the buffer, EPSG:6677
  sites.parquet     designated emergency evacuation sites (sites table) inside the buffer, EPSG:6677
  mesh1km.parquet   census 2020 population of 1 km meshes (JGD2011 table T001140) touching the buffer
and outputs/fetch_summary_b<buffer>.json with row counts.

EPSG:6677 is JGD2011 / Japan Plane Rectangular CS IX (metres), the zone for Tokyo.
"""
import argparse
import json
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE.parent / "outputs"

ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
OSM = "hf://datasets/yuiseki/osm-japan-src-2026-08@9a9b4a77e89e28a66bf15781644a16b63501f622/parquet"
SITES = "hf://datasets/yuiseki/gsi-evacuation-sites-jp@d8ad2169789b71c951e8808b2e54a953030aae07/parquet/sites.parquet"
MESH = "hf://datasets/yuiseki/estat-census-mesh-2020@6c486c8649484e09e549c0c99b5fa89b4f416edb/parquet/T001140.parquet"
TAITO = "13106"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buffer-m", type=int, default=5000)
    a = ap.parse_args()
    art = ROOT / f"artifacts/_evacuation_shelter/taito-bridge-cut-detour/raw_b{a.buffer_m}"
    art.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)

    c = duckdb.connect()
    c.execute("install spatial; load spatial; install httpfs; load httpfs; set threads=4")
    c.execute(f"""create table taito as select code5, name,
        st_transform(geometry, 'EPSG:4612', 'EPSG:6677', always_xy := true) g
        from '{ADMIN}' where code5 = '{TAITO}'""")
    n = c.execute("select count(*) from taito").fetchone()[0]
    assert n == 1, n
    c.execute(f"create table area as select st_buffer(g, {a.buffer_m}) g from taito")

    # bbox of the buffer in EPSG:3857 as constants (the card: constants let DuckDB skip row groups)
    xmin, ymin, xmax, ymax = c.execute("""select st_xmin(b), st_ymin(b), st_xmax(b), st_ymax(b) from
        (select st_transform(g, 'EPSG:6677', 'EPSG:3857', always_xy := true) b from area)""").fetchone()
    lon0, lat0, lon1, lat1 = c.execute("""select st_xmin(b), st_ymin(b), st_xmax(b), st_ymax(b) from
        (select st_transform(g, 'EPSG:6677', 'EPSG:4326', always_xy := true) b from area)""").fetchone()
    bb = f"bbox.xmin <= {xmax} and bbox.xmax >= {xmin} and bbox.ymin <= {ymax} and bbox.ymax >= {ymin}"

    c.execute(f"""create table lines as select osm_id, highway, railway, waterway, bridge, tunnel, layer, name,
        access, foot, service, covered, (tags->>'man_made') man_made, (tags->>'bridge:name') bridge_name,
        (tags->>'sidewalk') sidewalk, (tags->>'footway') footway,
        st_transform(way, 'EPSG:3857', 'EPSG:6677', always_xy := true) g
        from '{OSM}/planet_osm_line.parquet'
        where {bb} and (highway is not null or railway is not null or waterway is not null)""")
    c.execute("create table lines_in as select l.* from lines l, area a where st_intersects(l.g, a.g)")
    c.execute(f"""create table water as select osm_id, "natural" nat, waterway, water, name,
        st_transform(way, 'EPSG:3857', 'EPSG:6677', always_xy := true) g
        from '{OSM}/planet_osm_polygon.parquet'
        where {bb} and ("natural" = 'water' or waterway = 'riverbank')""")
    c.execute("create table water_in as select w.* from water w, area a where st_intersects(w.g, a.g)")
    c.execute(f"""create table sites as select common_id, name, municipality, earthquake, flood, large_fire,
        inland_flooding, storm_surge, tsunami, landslide, longitude, latitude,
        st_transform(st_point(longitude, latitude), 'EPSG:4326', 'EPSG:6677', always_xy := true) g
        from '{SITES}' where longitude between {lon0} and {lon1} and latitude between {lat0} and {lat1}""")
    c.execute("create table sites_in as select s.* from sites s, area a where st_within(s.g, a.g)")
    # 1 km meshes: south-west corner from the code (the card's formula), keep meshes whose box touches the bbox
    c.execute(f"""create table mesh as select KEY_CODE code, sum(try_cast(T001140001 as bigint)) pop,
        count(*) n_rows, min(HTKSYORI) htk_min, max(HTKSYORI) htk_max
        from '{MESH}' where prefecture in ('11', '12', '13', '14') group by KEY_CODE""")
    c.execute("""create table mesh_g as select code, pop, n_rows,
        cast(substr(code,1,2) as int)/1.5 + cast(substr(code,5,1) as int)*5/60.0 + cast(substr(code,7,1) as int)*30/3600.0 lat_s,
        cast(substr(code,3,2) as int) + 100 + cast(substr(code,6,1) as int)*7.5/60.0 + cast(substr(code,8,1) as int)*45/3600.0 lon_w
        from mesh""")
    c.execute(f"""create table mesh_in as select * from mesh_g
        where lon_w <= {lon1} and lon_w + 1/80.0 >= {lon0} and lat_s <= {lat1} and lat_s + 1/120.0 >= {lat0}""")

    for t, f in [("taito", "taito"), ("area", "area"), ("lines_in", "lines"), ("water_in", "water"),
                 ("sites_in", "sites"), ("mesh_in", "mesh1km")]:
        c.execute(f"copy {t} to '{art / (f + '.parquet')}' (format parquet)")

    q = lambda s: c.execute(s).fetchone()[0]
    summary = {
        "buffer_m": a.buffer_m,
        "bbox_3857": [xmin, ymin, xmax, ymax],
        "taito_area_km2": q("select st_area(g)/1e6 from taito"),
        "lines_bbox": q("select count(*) from lines"),
        "lines_in_buffer": q("select count(*) from lines_in"),
        "lines_highway": q("select count(*) from lines_in where highway is not null"),
        "lines_highway_bridge": q("select count(*) from lines_in where highway is not null and bridge is not null and bridge <> 'no'"),
        "lines_highway_tunnel": q("select count(*) from lines_in where highway is not null and tunnel is not null and tunnel <> 'no'"),
        "lines_railway": q("select count(*) from lines_in where railway is not null"),
        "lines_waterway": q("select count(*) from lines_in where waterway is not null"),
        "water_polygons": q("select count(*) from water_in"),
        "sites_in_buffer": q("select count(*) from sites_in"),
        "sites_earthquake": q("select count(*) from sites_in where earthquake"),
        "sites_flood": q("select count(*) from sites_in where flood"),
        "sites_large_fire": q("select count(*) from sites_in where large_fire"),
        "sites_in_taito_code": q(f"select count(*) from sites_in where substr(common_id, 2, 5) = '{TAITO}'"),
        "sites_in_taito_polygon": q("select count(*) from sites_in s, taito t where st_within(s.g, t.g)"),
        "mesh1km_rows": q("select count(*) from mesh_in"),
        "mesh1km_pop": q("select sum(pop) from mesh_in"),
        "mesh1km_multi_pref": q("select count(*) from mesh_in where n_rows > 1"),
        "highway_values": c.execute("select highway, count(*) n from lines_in where highway is not null group by 1 order by 2 desc").fetchall(),
        "bridge_values": c.execute("select bridge, count(*) n from lines_in where highway is not null and bridge is not null group by 1 order by 2 desc").fetchall(),
    }
    (OUT / f"fetch_summary_b{a.buffer_m}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith("values")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

"""Build the underpass populations of the 23 wards from frozen OSM and their labels (EXPERIMENT_PLAN.md).

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/01_build.py

Writes artifacts/_flood/tokyo23-underpass-listing/units_<population>.parquet (one row per unit: id, the
representative point x, y in EPSG:6677, road length, road class, form, the distance to the nearest point of the
national list and of the flood-prone points, and whether a flood record area touches it, touches it within 30 m, or
an inland-water (内水) record area touches it), unmatched_list_points.csv (list points with no main unit within
100 m; also copied to outputs/), and outputs/build_summary.json.

Populations: main (the plan's roads), service (main plus service roads), guard (roads under a railway bridge).
"""
import json
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/tokyo23-underpass-listing"
OUT = HERE.parent / "outputs"
OSM = "hf://datasets/yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664/parquet/planet_osm_line.parquet"
LIST = "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet"
KANSUI = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet"
RAW = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a/raw"  # wards (jp-admin-2026-09@e6c87b1), flood record (@354b0d9)
MAIN = ("'trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link',"
        "'unclassified','residential','living_street'")
CLASS = """case when highway in ('trunk','trunk_link','primary','primary_link') then 'trunk_primary'
               when highway in ('secondary','secondary_link','tertiary','tertiary_link') then 'secondary_tertiary'
               else 'minor' end"""
RANK = "case cls when 'trunk_primary' then 3 when 'secondary_tertiary' then 2 else 1 end"


def main():
    ART.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect()
    c.execute("load spatial; set threads=8")
    c.execute(f"create table wards as select code5, name, st_transform(geometry, 'EPSG:4612', 'EPSG:6677', always_xy := true) g from '{RAW / 'wards.parquet'}'")
    assert c.sql("select count(*) from wards").fetchall()[0][0] == 23
    c.execute("create table area as select st_union_agg(g) g from wards")
    c.execute(f"""create table l as select osm_id, highway, railway, tunnel, bridge, try_cast(layer as int) lay, name,
        st_transform(way, 'EPSG:3857', 'EPSG:6677', always_xy := true) g from '{OSM}'
        where highway is not null or railway is not null""")
    c.execute("create table lw as select l.* from l, area a where st_intersects(l.g, a.g)")
    below = "(tunnel in ('yes', 'covered') or lay < 0)"
    c.execute(f"create table road_main as select *, {CLASS} cls from lw where highway in ({MAIN}) and {below}")
    c.execute(f"create table road_service as select *, {CLASS} cls from lw where highway in ({MAIN}, 'service') and {below}")
    c.execute("""create table rail_bridge as select g from lw where railway in ('rail','subway','light_rail','monorail','narrow_gauge')
        and ((bridge is not null and bridge <> 'no') or lay > 0)""")
    c.execute(f"""create table road_guard as select r.osm_id, r.highway, r.tunnel, r.lay, {CLASS} cls, st_intersection(r.g, x.g) g
        from lw r, rail_bridge x where r.highway in ({MAIN}) and coalesce(r.lay, 0) <= 0 and (r.bridge is null or r.bridge = 'no')
        and st_intersects(r.g, x.g)""")
    c.execute(f"""create table pts_list as select u.id, u.name, u.manager, st_transform(st_point(u.lon, u.lat), 'OGC:CRS84', 'EPSG:6677', always_xy := true) p
        from '{LIST}' u, wards w where st_within(st_transform(st_point(u.lon, u.lat), 'OGC:CRS84', 'EPSG:6677', always_xy := true), w.g)""")
    c.execute(f"""create table pts_kansui as select k.fid, k.name, st_transform(st_point(k.lon, k.lat), 'OGC:CRS84', 'EPSG:6677', always_xy := true) p
        from '{KANSUI}' k where k.pref = '東京都'""")
    c.execute(f"""create table flood as select reason, st_transform(geometry, 'EPSG:4612', 'EPSG:6677', always_xy := true) g
        from '{RAW / 'flood_record_area.parquet'}'""")

    summary = {"wards": 23, "list_points_in_wards": c.sql("select count(*) from pts_list").fetchall()[0][0],
               "kansui_points_tokyo": c.sql("select count(*) from pts_kansui").fetchall()[0][0],
               "flood_areas": c.sql("select count(*) from flood").fetchall()[0][0], "populations": {}}
    for pop in ("main", "service", "guard"):
        src = f"road_{pop}"
        c.execute(f"""create or replace table u as select row_number() over () uid, geom g
            from (select unnest(st_dump(st_union_agg(st_buffer(g, 15)))).geom geom from {src})""")
        # roads of each unit: length, top class, form
        c.execute(f"""create or replace table ur as select u.uid, sum(st_length(st_intersection(r.g, u.g))) len_m,
            max({RANK.replace('cls', 'r.cls')}) rank,
            bool_or(r.tunnel = 'yes') has_tunnel, bool_or(r.tunnel = 'covered') has_covered
            from u join {src} r on st_intersects(u.g, r.g) group by u.uid""")
        c.execute(f"""create or replace table units as select u.uid,
            st_x(st_pointonsurface(u.g)) x, st_y(st_pointonsurface(u.g)) y, ur.len_m,
            case ur.rank when 3 then 'trunk_primary' when 2 then 'secondary_tertiary' else 'minor' end road_class,
            case when ur.has_tunnel then 'tunnel' when ur.has_covered then 'covered' else 'layer_only' end form,
            (select min(st_distance(u.g, p.p)) from pts_list p) d_list,
            (select min(st_distance(u.g, p.p)) from pts_kansui p) d_kansui,
            exists (select 1 from flood f where st_intersects(u.g, f.g)) flood,
            exists (select 1 from flood f where st_dwithin(u.g, f.g, 30)) flood30,
            exists (select 1 from flood f where f.reason = '内水' and st_intersects(u.g, f.g)) flood_naisui,
            st_aswkb(u.g) wkb
            from u join ur using (uid)""")
        n = c.sql("select count(*) from units").fetchall()[0][0]
        assert n == c.sql("select count(*) from u").fetchall()[0][0], "every unit must have its roads"
        c.execute(f"copy units to '{ART / f'units_{pop}.parquet'}' (format parquet)")
        summary["populations"][pop] = {"roads": c.sql(f"select count(*) from {src}").fetchall()[0][0], "units": n,
                                       "listed_100m": c.sql("select count(*) from units where d_list <= 100").fetchall()[0][0],
                                       "flood": c.sql("select count(*) from units where flood").fetchall()[0][0]}
        if pop == "main":
            c.execute(f"""copy (select p.id, p.name, p.manager, round(min(st_distance(p.p, u.g)), 1) d_nearest_unit_m
                from pts_list p, u group by all having min(st_distance(p.p, u.g)) > 100 order by 4)
                to '{ART / 'unmatched_list_points.csv'}' (header)""")
            c.execute(f"copy (select * from '{ART / 'unmatched_list_points.csv'}') to '{OUT / 'unmatched_list_points.csv'}' (header)")
            summary["list_points_without_main_unit_100m"] = c.sql(
                f"select count(*) from '{ART / 'unmatched_list_points.csv'}'").fetchall()[0][0]
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Cut the OSM road lines within 400 m of any underpass out of the Japan line table.

uvx --from 'duckdb>=1.5.5' python scripts/03_roads.py

Reads raw/planet_osm_line.parquet (osm-japan-src-2026-08@9a9b4a7, sha256 in README) and writes raw/roads.parquet: every
line with a highway value whose bbox comes within 400 m (ground, converted to EPSG:3857 units by 1 / cos(lat)) of a
point. All highway values are kept here; 04_profile.py chooses the classes of the plan. Lines are matched to points
through 1 km cells of EPSG:3857 so that no point x line product is formed.
"""
from pathlib import Path

import duckdb

ART = Path(__file__).resolve().parents[4] / "artifacts/_flood/underpass-ponding-exposure/raw"
CELL = 1000.0
NEAR = 400.0


def main():
    c = duckdb.connect()
    c.execute("load spatial")
    c.execute("set memory_limit = '6GB'")
    c.execute(f"""create table p as select id, lat,
            st_x(g) x, st_y(g) y, {NEAR} / cos(radians(lat)) r
        from (select id, lat, st_transform(st_point(lon, lat), 'EPSG:4326', 'EPSG:3857', always_xy := true) g
              from '{ART / 'underpass.parquet'}')""")
    c.execute(f"""create table pc as select id, cx, cy from p,
            range(floor((x - r) / {CELL})::bigint, floor((x + r) / {CELL})::bigint + 1) t1(cx),
            range(floor((y - r) / {CELL})::bigint, floor((y + r) / {CELL})::bigint + 1) t2(cy)""")
    c.execute(f"""create table l as select osm_id, highway, name, ref, bridge, tunnel, layer, covered,
            bbox, way from '{ART / 'planet_osm_line.parquet'}' where highway is not null""")
    n_hw = c.execute("select count(*) from l").fetchone()[0]
    # lines longer than 50 cells are few; test them against every point instead of enumerating their cells
    long = f"(bbox.xmax - bbox.xmin) >= 50 * {CELL} or (bbox.ymax - bbox.ymin) >= 50 * {CELL}"
    c.execute(f"""create table lc as select l.rowid rid, cx, cy from l,
            range(floor(bbox.xmin / {CELL})::bigint, floor(bbox.xmax / {CELL})::bigint + 1) t1(cx),
            range(floor(bbox.ymin / {CELL})::bigint, floor(bbox.ymax / {CELL})::bigint + 1) t2(cy)
        where not ({long})""")
    c.execute("""create table keep as select distinct lc.rid from lc join pc using (cx, cy)
        join p using (id) join l on l.rowid = lc.rid
        where l.bbox.xmin <= p.x + p.r and l.bbox.xmax >= p.x - p.r and l.bbox.ymin <= p.y + p.r and l.bbox.ymax >= p.y - p.r""")
    n_long = c.execute(f"""insert into keep select distinct l.rowid from l join p
        on l.bbox.xmin <= p.x + p.r and l.bbox.xmax >= p.x - p.r and l.bbox.ymin <= p.y + p.r and l.bbox.ymax >= p.y - p.r
        where {long}""").fetchone()[0]
    c.execute(f"""copy (select * from l where rowid in (select rid from keep) order by osm_id)
        to '{ART / 'roads.parquet'}' (format parquet)""")
    n = c.execute(f"select count(*), count(distinct osm_id) from '{ART / 'roads.parquet'}'").fetchone()
    print({"highway_lines": n_hw, "kept_rows": n[0], "kept_osm_ids": n[1], "long_lines_kept": n_long})


if __name__ == "__main__":
    main()

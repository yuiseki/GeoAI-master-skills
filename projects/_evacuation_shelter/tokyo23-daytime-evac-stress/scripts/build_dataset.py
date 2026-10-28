"""Build the 1 km mesh dataset for the daytime evacuation-stress question.

Outputs (artifacts/_evacuation_shelter/tokyo23-daytime-evac-stress/):
  mesh_dataset.parquet  one row per 1 km mesh whose center is inside the 23 wards
  blocks.parquet        the same values aggregated to 2 km, 4 km and shifted 2 km blocks
  build_audit.json      inputs, versions, counts and the derivation record

Run: ~/.venvs/geoai/bin/python scripts/build_dataset.py
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
OUT = ROOT / "artifacts" / "tokyo23-daytime-evac-stress"
OUT.mkdir(parents=True, exist_ok=True)

MLIT = "hf://datasets/yuiseki/mlit-1km-fromto-2022-01@2424a9d9a0518f5575f0af54602eb428ca6d97b2/parquet"
CENSUS = "hf://datasets/yuiseki/estat-census-mesh-2020@6c486c8649484e09e549c0c99b5fa89b4f416edb/parquet/T001140.parquet"
SITES = "hf://datasets/yuiseki/gsi-evacuation-sites-jp@d8ad2169789b71c951e8808b2e54a953030aae07/parquet/sites.parquet"
SHELTERS = "hf://datasets/yuiseki/gsi-evacuation-sites-jp@d8ad2169789b71c951e8808b2e54a953030aae07/parquet/shelters.parquet"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"

VERSIONS = {
    "yuiseki/mlit-1km-fromto-2022-01": "2424a9d9a0518f5575f0af54602eb428ca6d97b2",
    "yuiseki/estat-census-mesh-2020": "6c486c8649484e09e549c0c99b5fa89b4f416edb",
    "yuiseki/gsi-evacuation-sites-jp": "d8ad2169789b71c951e8808b2e54a953030aae07",
    "yuiseki/jp-admin-2026-09": "e6c87b1d7095c17422147962185071a986e13135",
}


def main():
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET geometry_always_xy = true;")

    con.execute(f"""
        create temp table wards as
        select code5, name, geometry
        from read_parquet('{ADMIN}') where code5 between '13101' and '13123'
    """)

    # 1 km mesh grid: center point in the 23 wards, projected for distance work.
    con.execute(f"""
        create temp table mesh_pts as
        select m.mesh1kmid, m.citycode,
               cast(m.lon_center as double) lon, cast(m.lat_center as double) lat,
               w.code5 ward_code, w.name ward,
               ST_Transform(ST_SetCRS(ST_Point(cast(m.lon_center as double),
                                                cast(m.lat_center as double)), 'EPSG:4612'),
                            'EPSG:6677') g
        from read_parquet('{MLIT}/attribute_mesh1km.parquet') m
        join wards w
          on ST_Within(ST_SetCRS(ST_Point(cast(m.lon_center as double),
                                          cast(m.lat_center as double)), 'EPSG:4612'), w.geometry)
        where m.version = '2020'
    """)

    con.execute("""
        create temp table census as
        select KEY_CODE, sum(try_cast(T001140001 as bigint)) night
        from read_parquet('%s') group by 1
    """ % CENSUS)

    con.execute(f"""
        create temp table daytime as
        select mesh1kmid,
               max(population) filter (where year = '2019') day19,
               max(population) filter (where year = '2021') day21
        from read_parquet('{MLIT}/monthly_mdp_mesh1km.parquet')
        where prefcode = '13' and month = '10' and dayflag = '1' and timezone = '0'
          and year in ('2019', '2021')
        group by 1
    """)

    # Shelter points (designated evacuation shelters) and earthquake sites, projected.
    con.execute(f"""
        create temp table shelters as
        select common_id, substr(common_id, 2, 5) as ward_code,
               substr(common_id, 2, 5) between '13101' and '13123' as in23,
               ST_Transform(geometry, 'EPSG:6677') g
        from read_parquet('{SHELTERS}')
    """)
    con.execute(f"""
        create temp table eq_sites as
        select common_id, substr(common_id, 2, 5) as ward_code,
               ST_Transform(geometry, 'EPSG:6677') g
        from read_parquet('{SITES}') where earthquake
    """)

    con.execute("""
        create temp table shelter_pairs as
        select m.mesh1kmid, s.common_id, s.in23, ST_Distance(m.g, s.g) d
        from mesh_pts m join shelters s on ST_DWithin(m.g, s.g, 5000)
    """)
    con.execute("""
        create temp table eq_pairs as
        select m.mesh1kmid, e.common_id, e.ward_code, ST_Distance(m.g, e.g) d
        from mesh_pts m join eq_sites e on ST_DWithin(m.g, e.g, 1500)
    """)

    con.execute("""
        create temp table ward_eq as
        select w.code5, count(e.common_id) eq_sites
        from wards w left join eq_sites e on e.ward_code = w.code5
        group by 1
    """)

    con.execute("""
        create temp table sh_agg as
        select mesh1kmid,
               count(common_id) filter (where d <= 500) as sh_500,
               count(common_id) filter (where d <= 1000) as sh_1000,
               count(common_id) filter (where d <= 1500) as sh_1500,
               count(common_id) filter (where d <= 1000 and in23) as sh_1000_23,
               min(d) as nearest_sh_m
        from shelter_pairs
        group by 1
    """)
    con.execute("""
        create temp table eq_agg as
        select mesh1kmid,
               count(common_id) filter (where d <= 1000) as eq_1000,
               count(common_id) filter (where d <= 1500) as eq_1500,
               min(d) as nearest_eq_m
        from eq_pairs
        group by 1
    """)

    con.execute("""
        create temp table mesh_data as
        select m.mesh1kmid, m.ward_code, m.ward, m.lon, m.lat,
               coalesce(c.night, 0) as night,
               coalesce(d.day19, 0) as day19,
               coalesce(d.day21, 0) as day21,
               (c.KEY_CODE is not null) as census_row,
               (d.day19 is not null) as day19_row,
               (d.day21 is not null) as day21_row,
               (we.eq_sites > 0) as eq_published,
               coalesce(we.eq_sites, 0) as ward_eq_sites,
               coalesce(sa.sh_500, 0) as sh_500,
               coalesce(sa.sh_1000, 0) as sh_1000,
               coalesce(sa.sh_1500, 0) as sh_1500,
               coalesce(sa.sh_1000_23, 0) as sh_1000_23,
               sa.nearest_sh_m,
               coalesce(ea.eq_1000, 0) as eq_1000,
               coalesce(ea.eq_1500, 0) as eq_1500,
               ea.nearest_eq_m
        from mesh_pts m
        left join census c on c.KEY_CODE = m.mesh1kmid
        left join daytime d on d.mesh1kmid = m.mesh1kmid
        left join ward_eq we on we.code5 = m.ward_code
        left join sh_agg sa on sa.mesh1kmid = m.mesh1kmid
        left join eq_agg ea on ea.mesh1kmid = m.mesh1kmid
    """)

    # Global 1 km row/column index from the standard mesh code, then aligned and shifted blocks.
    con.execute("""
        create temp table block_assign as
        select *,
               (cast(substr(mesh1kmid,1,2) as int) * 80
                + cast(substr(mesh1kmid,5,1) as int) * 10
                + cast(substr(mesh1kmid,7,1) as int)) as mesh_row,
               (cast(substr(mesh1kmid,3,2) as int) * 80
                + cast(substr(mesh1kmid,6,1) as int) * 10
                + cast(substr(mesh1kmid,8,1) as int)) as mesh_col
        from mesh_data
    """)
    con.execute("""
        create temp table block_members as
        select scale, block_id, mesh1kmid from (
          select '1km' as scale, mesh1kmid as block_id, mesh1kmid
          from block_assign
          union all
          select '2km', '2_' || (mesh_row // 2) || '_' || (mesh_col // 2), mesh1kmid
          from block_assign
          union all
          select '2km_shift', 's2_' || ((mesh_row + 1) // 2) || '_' || ((mesh_col + 1) // 2), mesh1kmid
          from block_assign
          union all
          select '4km', '4_' || (mesh_row // 4) || '_' || (mesh_col // 4), mesh1kmid
          from block_assign
        )
    """)
    con.execute("""
        create temp table block_pop as
        select b.scale, b.block_id,
               count(*) as n_meshes,
               sum(d.night) as night, sum(d.day19) as day19, sum(d.day21) as day21,
               avg(d.lon) as lon, avg(d.lat) as lat,
               mode(d.ward) as ward,
               string_agg(distinct d.ward, ',') as wards
        from block_members b join mesh_data d using (mesh1kmid)
        group by 1, 2
    """)
    con.execute("""
        create temp table block_sh as
        select b.scale, b.block_id, count(distinct s.common_id) as sh_1000
        from block_members b
        join mesh_pts m using (mesh1kmid)
        join shelters s on ST_DWithin(m.g, s.g, 1000)
        group by 1, 2
    """)
    con.execute("""
        create temp table block_eq as
        select b.scale, b.block_id, count(distinct e.common_id) as eq_1000
        from block_members b
        join mesh_pts m using (mesh1kmid)
        join eq_sites e on ST_DWithin(m.g, e.g, 1000)
        group by 1, 2
    """)
    con.execute("""
        create temp table blocks as
        select p.*, coalesce(s.sh_1000, 0) as sh_1000, coalesce(e.eq_1000, 0) as eq_1000
        from block_pop p
        left join block_sh s using (scale, block_id)
        left join block_eq e using (scale, block_id)
    """)

    con.execute(f"COPY mesh_data TO '{OUT / 'mesh_dataset.parquet'}' (FORMAT parquet)")
    con.execute(f"COPY blocks TO '{OUT / 'blocks.parquet'}' (FORMAT parquet)")

    counts = con.sql("""
        select count(*) as meshes,
               count(*) filter (where sh_1000 = 0) as zero_shelter_meshes,
               count(*) filter (where sh_1000 > 0) as finite_meshes,
               count(*) filter (where census_row) as census_rows,
               count(*) filter (where day19_row) as day19_rows,
               count(*) filter (where day21_row) as day21_rows,
               sum(night) as night_total,
               sum(day19) as day19_total,
               sum(day21) as day21_total,
               count(*) filter (where nearest_sh_m is null) as no_shelter_within_5km,
               count(*) filter (where eq_published) as meshes_eq_published,
               count(*) filter (where ward_eq_sites > 0) as meshes_in_eq_published_ward
        from mesh_data
    """).fetchall()[0]
    keys = ["meshes", "zero_shelter_meshes", "finite_meshes", "census_rows", "day19_rows",
            "day21_rows", "night_total", "day19_total", "day21_total", "no_shelter_within_5km",
            "meshes_eq_published", "meshes_in_eq_published_ward"]
    counts = dict(zip(keys, counts))

    block_counts = con.sql("""
        select scale, count(*) blocks, count(*) filter (where sh_1000 = 0) zero_blocks,
               sum(n_meshes) member_sum
        from blocks group by 1 order by 1
    """).fetchall()

    ward_eq = con.sql("select code5, eq_sites from ward_eq order by code5").fetchall()

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = "unknown"

    audit = {
        "derived": True,
        "note": "Derived table: buffered shelter/site counts around mesh centers, not observations.",
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "projects/_evacuation_shelter/tokyo23-daytime-evac-stress/scripts/build_dataset.py",
        "git_commit": commit,
        "tool": f"duckdb {duckdb.__version__}, spatial + httpfs",
        "inputs": VERSIONS,
        "definitions": {
            "unit": "1 km mesh (8-digit standard mesh code); center inside a 2020 ward polygon (code5 13101-13123)",
            "night_population": "2020 census T001140001 summed by KEY_CODE (prefecture rows added)",
            "day_population": "MLIT 1 km flow, October, weekday (dayflag=1), daytime 11-14 (timezone=0), 1-day monthly average; missing rows (<10 people) set to 0",
            "shelter_count": "designated evacuation shelters (shelters table) within radius of the mesh center, EPSG:6677 metres; all shelters, including outside the 23 wards",
            "eq_site_count": "earthquake-designated emergency sites (sites.earthquake=true) within radius; only 13 wards publish any",
        },
        "counts": counts,
        "blocks": [{"scale": s, "blocks": b, "zero_shelter_blocks": z, "member_sum": m}
                   for s, b, z, m in block_counts],
        "ward_eq_sites": {code: n for code, n in ward_eq},
        "assumptions_not_verified": [
            "shelter registry completeness per ward",
            "facility capacity proportional to facility count",
            "straight-line 1 km radius ignores rivers, rail, road closure",
            "2019 daytime flow and 2020 census are different years",
        ],
    }
    (OUT / "build_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(audit["blocks"], ensure_ascii=False))
    print("blocks by scale:", block_counts)


if __name__ == "__main__":
    main()

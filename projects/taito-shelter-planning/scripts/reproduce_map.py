"""Map census population density and shelter siting trade-offs in Taito with analysis-visualize."""

import csv
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE = ROOT / "projects/tokyo-town-types/tmp/source"
COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/spatial_result_map.py"

TAITO_LANDMARK_TOWNS = (
    "上野公園",
    "谷中",
    "池之端",
    "上野桜木",
    "根岸",
    "入谷",
    "三ノ輪",
    "日本堤",
    "清川",
    "橋場",
    "今戸",
    "千束",
    "竜泉",
    "下谷",
    "上野",
    "東上野",
    "秋葉原",
    "台東",
    "松が谷",
    "西浅草",
    "浅草",
    "雷門",
    "元浅草",
    "蔵前",
    "鳥越",
    "浅草橋",
)


def validate_towns(rows, expected_population):
    ids = [row[0] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate town ID")
    for _, population, area, density in rows:
        if not math.isfinite(area) or area <= 0:
            raise ValueError("area must be positive")
        if not math.isfinite(population) or population < 0:
            raise ValueError("population must be nonnegative")
        if not math.isclose(population / area, density, rel_tol=1e-6):
            raise ValueError("density does not match population / area")
    if not math.isclose(sum(row[1] for row in rows), expected_population, abs_tol=0.5):
        raise ValueError("population total differs from the pinned report")
    return len(rows)


def _draw(name, fc, config):
    temp = PROJECT / "tmp"
    temp.mkdir(exist_ok=True)
    input_path = temp / f"{name}.geojson"
    config_path = temp / f"{name}.json"
    input_path.write_text(json.dumps(fc, ensure_ascii=False))
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    output = PROJECT / "outputs" / f"{name}.png"
    subprocess.run([sys.executable, str(DRAW), str(input_path), str(config_path), str(output)], check=True)
    return output


def _load_source(relative, name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    revision = subprocess.check_output(["git", "-C", SOURCE, "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"expected source commit {COMMIT}, got {revision}")
    sys.path.insert(0, str(SOURCE / "src"))
    import numpy as np
    from study_geoai import aoi, ckan, cover, features, ksj, osm
    from study_geoai.db import connect

    con = connect()
    taito = aoi.load("taito", con)
    relation = features.small_areas(con, taito)
    relation.create_view("towns")
    rows = con.sql(
        "select key11, population, area_km2, density, name, st_asgeojson(geometry) from towns order by key11"
    ).fetchall()
    if validate_towns([r[:4] for r in rows], 211444) != 108:
        raise RuntimeError(f"expected 108 towns, got {len(rows)}")

    wards_path = aoi._wards(con)
    neighbor_rows = con.execute(
        """
        select name, st_asgeojson(geometry)
        from read_parquet(?)
        where name in ('台東区', '文京区', '荒川区', '墨田区', '千代田区', '中央区')
        order by code5
        """,
        [str(wards_path)],
    ).fetchall()
    neighbor_areas = [{"name": "", "geometry": json.loads(g)} for _, g in neighbor_rows]

    town_base_rows = con.sql(
        """
        select regexp_replace(name, '[一二三四五六七八九十]+丁目$', '') as base_name,
               st_asgeojson(st_union_agg(geometry)) as geom
        from towns
        group by 1
        """
    ).fetchall()
    by_base = {r[0]: json.loads(r[1]) for r in town_base_rows}
    landmarks = [{"name": t, "geometry": by_base[t]} for t in TAITO_LANDMARK_TOWNS if t in by_base]

    osm.roads(con, taito).create_view("_taito_roads")
    road_rows = con.execute(
        """
        with clipped as (
            select highway,
                   st_intersection(
                       st_transform(geometry, 'EPSG:6677', 'EPSG:4326', always_xy := true),
                       st_geomfromtext(?)
                   ) as g
            from _taito_roads
            where highway in (
                'motorway', 'trunk', 'primary', 'secondary', 'tertiary',
                'motorway_link', 'trunk_link', 'primary_link', 'secondary_link'
            )
        )
        select case when highway in ('tertiary') then 'minor' else 'major' end as tier,
               st_asgeojson(g)
        from clipped
        where not st_isempty(g)
          and st_geometrytype(g) in ('LINESTRING', 'MULTILINESTRING')
        """,
        [taito.wkt],
    ).fetchall()
    roads = [{"tier": tier, "geometry": json.loads(g)} for tier, g in road_rows]
    taito_outline = json.loads(
        con.execute("select st_asgeojson(st_geomfromtext(?))", [taito.wkt]).fetchone()[0]
    )

    sorted_by_density = sorted(rows, key=lambda r: -float(r[3]))
    top3 = sorted_by_density[:3]
    min_town = sorted_by_density[-1]
    density_highlights = [
        {
            "id": str(r[0]),
            "rank": str(idx),
            "label": f"{r[4]} ({r[3]:,.0f} 人/km²、{int(r[1]):,} 人)",
            "color": "#8E2675",
        }
        for idx, r in enumerate(top3, 1)
    ] + [
        {
            "id": str(min_town[0]),
            "rank": "4",
            "label": f"最小: {min_town[4]} ({min_town[3]:,.0f} 人/km²、{int(min_town[1]):,} 人)",
            "color": "#0B556C",
        }
    ]

    density_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": str(r[0]), "name": r[4], "value": float(r[3])},
                "geometry": json.loads(r[5]),
            }
            for r in rows
        ],
    }
    _draw(
        "taito-population-density",
        density_fc,
        {
            "question": "台東区のどの町丁目に人口が集中しているか (2020年国勢調査)",
            "value": "value",
            "kind": "sequential",
            "class_method": "quantile",
            "classes": 5,
            "compare_methods": ["equal"],
            "palette": "YlOrRd",
            "value_unit": "人/km²",
            "unit": "町丁目",
            "expect_units": 108,
            "crs": "OGC:CRS84",
            "source": f"census 2020; study-geoai-algo-py {COMMIT[:8]}",
            "source_commit": COMMIT,
            "geometry_source": "国勢調査2020の町丁目境界 (estat-boundary-2020@823195c)",
            "data_version": "国勢調査2020 (211,444人) / OSM道路 e60e017f6a77",
            "method": "分位5階級 (等間隔5階級との入れ替わり率を記録)",
            "outline": taito_outline,
            "context_areas": neighbor_areas,
            "roads": roads,
            "highlights": density_highlights,
            "landmarks": landmarks,
            "landmark_fontsize": 7.8,
            "stop_on_overlap": True,
        },
    )

    step12a = _load_source("src/012-A-multi-objective-optimization/run.py", "step12a")
    pop, sets, flood, site_xy, site_names = step12a.instance(con)
    con.execute("create or replace temp table _cand_xy (i integer, x double, y double)")
    con.executemany(
        "insert into _cand_xy values (?, ?, ?)",
        [(i, float(xy[0]), float(xy[1])) for i, xy in enumerate(site_xy)],
    )
    cand_lonlat_rows = con.sql(
        """
        select c.i,
               st_x(p) as lon,
               st_y(p) as lat,
               coalesce(t.name, '区外・境界上') as town_name
        from (
            select i,
                   st_transform(st_point(x, y), 'EPSG:6677', 'EPSG:4326', always_xy := true) as p
            from _cand_xy
        ) c
        left join towns t on st_contains(t.geometry, c.p)
        order by c.i
        """
    ).fetchall()
    cand_lonlat = [(float(r[1]), float(r[2])) for r in cand_lonlat_rows]
    cand_towns = [str(r[3]) for r in cand_lonlat_rows]

    ksj.read(con, taito, "A31a").create_view("_flood_poly")
    town_flood_rows = con.sql(
        """
        with f as (
            select cast(A31a_205 as integer) as rank,
                   st_transform(geometry, 'EPSG:6668', 'EPSG:4326', always_xy := true) as g
            from _flood_poly
            where source_file like 'A31a-20-%'
        )
        select t.key11, coalesce(max(f.rank), 0) as max_rank
        from towns t
        left join f on st_intersects(f.g, st_pointonsurface(t.geometry))
        group by t.key11
        order by t.key11
        """
    ).fetchall()
    town_flood_by_key = {str(r[0]): int(r[1]) for r in town_flood_rows}

    sol_zero = cover.solve_multi(sets, pop, flood, k=13, max_flood=0)
    sol_four = cover.solve_multi(sets, pop, flood, k=13, max_flood=4)
    sol_twentyone = cover.solve_multi(sets, pop, flood, k=13, max_flood=21)
    sol_free = cover.solve_multi(sets, pop, flood, k=13, max_flood=33)
    for label, sol in (
        ("max_flood=0", sol_zero),
        ("max_flood=4", sol_four),
        ("max_flood=21", sol_twentyone),
        ("max_flood=33", sol_free),
    ):
        if sol.get("status") != "Optimal":
            raise RuntimeError(f"{label} failed: {sol.get('status')}")

    idx_zero = np.flatnonzero(sol_zero["x"] > 0.5).tolist()
    idx_free = np.flatnonzero(sol_free["x"] > 0.5).tolist()

    with (PROJECT / "outputs/selected-sites.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["regime", "max_flood_limit", "site_index", "facility_name", "town", "flood_rank", "lon", "lat"])
        for regime, limit, sol in (
            ("浸水上限0 (21.1%)", "0", sol_zero),
            ("浸水上限4 (28.2%)", "4", sol_four),
            ("浸水上限21 (48.7%)", "21", sol_twentyone),
            ("最大カバーパレート解 (上限33: 52.9%)", "33", sol_free),
        ):
            for j in np.flatnonzero(sol["x"] > 0.5).tolist():
                lon, lat = cand_lonlat[j]
                writer.writerow([regime, limit, j, site_names[j], cand_towns[j], int(flood[j]), round(lon, 6), round(lat, 6)])

    flood_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": str(r[0]),
                    "name": r[4],
                    "value": int(town_flood_by_key[str(r[0])]),
                },
                "geometry": json.loads(r[5]),
            }
            for r in rows
        ],
    }
    flood_rank_counts = np.bincount(flood.astype(int), minlength=5).tolist()
    _draw(
        "taito-shelter-siting",
        flood_fc,
        {
            "question": "浸水ランクの上限で、566候補地と13拠点の配置はどう変わるか",
            "value": "value",
            "kind": "category",
            "categories": {
                "0": "町丁目代表点が浸水想定外 (ランク0)",
                "1": "浸水0.5m未満 (ランク1)",
                "2": "浸水0.5〜3m (ランク2)",
                "3": "浸水3〜5m (ランク3)",
            },
            "category_colors": {
                "0": "#F4EFE6",
                "1": "#D0E1F2",
                "2": "#94C4DF",
                "3": "#4A98C9",
            },
            "unit": "町丁目",
            "expect_units": 108,
            "crs": "OGC:CRS84",
            "source": f"study-geoai-algo-py {COMMIT[:8]}; KSJ P04/P29/A31a; WorldPop 2025",
            "source_commit": COMMIT,
            "geometry_source": "国勢調査2020の町丁目境界 (estat-boundary-2020@823195c)",
            "data_version": "WorldPop 2025 (209,240人) / 国土数値情報 P04・P29・A31a / OSM道路 e60e017f6a77",
            "method": "k=13 最大被覆 MILP (浸水ランク上限0 vs 浸水制約なし)",
            "outline": taito_outline,
            "context_areas": neighbor_areas,
            "roads": roads,
            "point_groups": [
                {
                    "label": f"浸水区域内の候補地 (ランク1〜4: {sum(flood_rank_counts[1:])}か所)",
                    "color": "#555555",
                    "edgecolor": "white",
                    "marker": "o",
                    "size": 16,
                    "linewidth": 0.35,
                    "alpha": 0.55,
                    "zorder": 5.2,
                    "points": [
                        [cand_lonlat[i][0], cand_lonlat[i][1]]
                        for i in range(len(flood))
                        if flood[i] > 0
                    ],
                },
                {
                    "label": f"浸水想定外の候補地 (ランク0: {flood_rank_counts[0]}か所)",
                    "color": "#FFFFFF",
                    "edgecolor": "#00695C",
                    "marker": "o",
                    "size": 24,
                    "linewidth": 0.9,
                    "alpha": 0.9,
                    "zorder": 5.5,
                    "points": [
                        [cand_lonlat[i][0], cand_lonlat[i][1]]
                        for i in range(len(flood))
                        if flood[i] == 0
                    ],
                },
                {
                    "label": "浸水上限0の13拠点 (21.1%カバー: 西側台地に集中)",
                    "color": "#00695C",
                    "edgecolor": "white",
                    "marker": "^",
                    "size": 86,
                    "linewidth": 1.0,
                    "alpha": 0.98,
                    "zorder": 6.6,
                    "points": [[cand_lonlat[i][0], cand_lonlat[i][1]] for i in idx_zero],
                },
                {
                    "label": "最大カバー解の13拠点 (ランク和33、52.9%カバー: 人口密集地へ分散)",
                    "color": "#C62828",
                    "edgecolor": "white",
                    "marker": "s",
                    "size": 70,
                    "linewidth": 1.0,
                    "alpha": 0.96,
                    "zorder": 6.4,
                    "points": [[cand_lonlat[i][0], cand_lonlat[i][1]] for i in idx_free],
                },
            ],
            "landmarks": landmarks,
            "landmark_fontsize": 7.8,
            "stop_on_overlap": True,
        },
    )

    existing_rows = (
        ckan.facilities(con, taito, "指定緊急避難場所一覧")
        .query(
            "f",
            """
            select name, lon, lat,
                   cast(attributes->>'$.想定収容人数' as integer) as cap,
                   coalesce(attributes->>'$.備考', '') as note
            from f where status = 'ok' order by row
            """,
        )
        .fetchall()
    )
    open_pts = []
    closed_pts = []
    open_Idx = 0
    with (PROJECT / "outputs/existing-shelters.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "lon", "lat", "capacity", "arakawa_open", "note"])
        for nm, lon, lat, cap, note in existing_rows:
            is_open = "荒川が氾濫" not in note
            writer.writerow([nm, round(float(lon), 6), round(float(lat), 6), int(cap), is_open, note])
            if is_open:
                open_Idx += 1
                open_pts.append({"x": float(lon), "y": float(lat), "rank": str(open_Idx)})
            else:
                closed_pts.append([float(lon), float(lat)])

    _draw(
        "taito-existing-shelters",
        flood_fc,
        {
            "question": "既存の指定緊急避難場所17か所はどこにあり、荒川氾濫時にどこが開くか",
            "value": "value",
            "kind": "category",
            "categories": {
                "0": "町丁目代表点が浸水想定外 (ランク0)",
                "1": "浸水0.5m未満 (ランク1)",
                "2": "浸水0.5〜3m (ランク2)",
                "3": "浸水3〜5m (ランク3)",
            },
            "category_colors": {
                "0": "#F4EFE6",
                "1": "#D0E1F2",
                "2": "#94C4DF",
                "3": "#4A98C9",
            },
            "unit": "町丁目",
            "expect_units": 108,
            "crs": "OGC:CRS84",
            "source": f"study-geoai-algo-py {COMMIT[:8]}; tokyo-ckan 指定緊急避難場所一覧; KSJ A31a",
            "source_commit": COMMIT,
            "geometry_source": "国勢調査2020の町丁目境界 (estat-boundary-2020@823195c)",
            "data_version": "東京都オープンデータ (指定緊急避難場所17か所・計2,244人分) / 国土数値情報 A31a / OSM道路 e60e017f6a77",
            "method": "指定緊急避難場所の備考欄による荒川氾濫時の開設可否分類",
            "outline": taito_outline,
            "context_areas": neighbor_areas,
            "roads": roads,
            "point_groups": [
                {
                    "label": "荒川氾濫のおそれ時に開設しない (14か所・計1,870人分)",
                    "color": "#666666",
                    "edgecolor": "white",
                    "marker": "o",
                    "size": 52,
                    "linewidth": 0.9,
                    "alpha": 0.9,
                    "zorder": 6.2,
                    "points": closed_pts,
                },
                {
                    "label": "荒川氾濫時も開設 (1〜3の3か所・計374人分)",
                    "color": "#C62828",
                    "edgecolor": "white",
                    "marker": "^",
                    "size": 95,
                    "linewidth": 1.1,
                    "alpha": 0.98,
                    "zorder": 6.6,
                    "points": open_pts,
                },
            ],
            "landmarks": landmarks,
            "landmark_fontsize": 7.8,
            "stop_on_overlap": True,
        },
    )

    total_wp = float(pop.sum())
    summary = {
        "n_towns": len(rows),
        "census_population": int(sum(r[1] for r in rows)),
        "density_min": round(float(min_town[3]), 1),
        "density_max": round(float(top3[0][3]), 0),
        "worldpop_cells": len(pop),
        "worldpop_population": round(total_wp),
        "k_sites": 13,
        "radius_m": 400,
        "pareto_solutions_epsilon": 34,
        "weighted_sum_solutions": 12,
        "candidates_total": len(flood),
        "candidates_flood_rank_0": int(flood_rank_counts[0]),
        "candidates_in_flood_zone": int(sum(flood_rank_counts[1:])),
        "candidates_in_flood_zone_share": round(sum(flood_rank_counts[1:]) / len(flood), 3),
        "coverage_share_max_flood_0": round(sol_zero["covered"] / total_wp, 3),
        "coverage_share_max_flood_4": round(sol_four["covered"] / total_wp, 3),
        "coverage_share_max_flood_21": round(sol_twentyone["covered"] / total_wp, 3),
        "coverage_share_unconstrained": round(sol_free["covered"] / total_wp, 3),
        "unconstrained_flood_rank_sum": int(round(sol_free["flood"])),
        "existing_shelters_count": 17,
        "existing_shelters_coverage_400m_share": 0.337,
        "arakawa_open_shelters_count": 3,
        "arakawa_open_shelters_capacity": 374,
        "arakawa_1pct_demand": 2111,
        "random_placements_trials": 2000,
    }
    (PROJECT / "outputs/shelter-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"{len(rows)} towns; total census population {sum(row[1] for row in rows):,.0f}")


if __name__ == "__main__":
    main()

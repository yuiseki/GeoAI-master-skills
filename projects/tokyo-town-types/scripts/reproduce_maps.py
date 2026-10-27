"""Reproduce town-type maps from the pinned original analysis and its data readers.

Run from the repository root after cloning the source into this project's tmp/source.
The original code reads versioned public sources and caches them in /tmp/study-geoai.
"""

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE = PROJECT / "tmp/source"
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


def feature_collection(ids, geojson, values):
    if len(ids) != len(geojson) or len(ids) != len(values):
        raise ValueError("row count mismatch between ids, geometries and values")
    if len(set(map(str, ids))) != len(ids):
        raise ValueError("duplicate unit id")
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": str(identifier), "value": float(value)},
                "geometry": json.loads(geometry),
            }
            for identifier, geometry, value in zip(ids, geojson, values, strict=True)
        ],
    }


def source_module(name, relative):
    path = SOURCE / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def draw(name, data, config):
    temp = PROJECT / "tmp"
    temp.mkdir(exist_ok=True)
    input_path = temp / f"{name}.geojson"
    config_path = temp / f"{name}.json"
    input_path.write_text(json.dumps(data, ensure_ascii=False))
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    output = PROJECT / "outputs" / f"{name}.png"
    subprocess.run([sys.executable, DRAW, input_path, config_path, output], check=True)
    return output


def _taito_context_and_landmarks(con, taito):
    from study_geoai import census, osm

    census.small_areas(con, taito).create_view("_taito_sa")
    chome_rows = con.sql(
        "select name, st_asgeojson(geometry) from _taito_sa order by key11"
    ).fetchall()
    chome_areas = [
        {"name": "", "geometry": json.loads(g)} for _, g in chome_rows
    ]
    town_rows = con.sql(
        """
        select regexp_replace(name, '[一二三四五六七八九十]+丁目$', '') as base_name,
               st_asgeojson(st_union_agg(geometry)) as geom
        from _taito_sa
        group by 1
        """
    ).fetchall()
    by_base = {r[0]: json.loads(r[1]) for r in town_rows}
    landmarks = [
        {"name": t, "geometry": by_base[t]}
        for t in TAITO_LANDMARK_TOWNS
        if t in by_base
    ]

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
    return chome_areas, landmarks, roads


def _tokyo23_ward_context(con):
    from study_geoai import aoi

    wards_path = aoi._wards(con)
    rows = con.execute(
        "select name, st_asgeojson(geometry) from read_parquet(?) order by code5",
        [str(wards_path)],
    ).fetchall()
    return [{"name": name, "geometry": json.loads(g)} for name, g in rows]


def main():
    revision = subprocess.run(
        ["git", "-C", SOURCE, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if revision.returncode != 0 or revision.stdout.strip() != COMMIT:
        raise RuntimeError(f"clone study-geoai-algo-py at {COMMIT} into {SOURCE} first")
    sys.path.insert(0, str(SOURCE / "src"))
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import adjusted_rand_score
    from sklearn.preprocessing import StandardScaler
    from study_geoai import aoi, features
    from study_geoai.db import connect

    original_a = source_module("original_town_clusters", "src/005-A-k-means/run.py")
    original_c = source_module("original_grid_clusters", "src/005-C-grid-types/run.py")
    original_d = source_module("original_dpmm", "src/005-D-dpmm/run.py")
    original_pc = source_module("original_street_pca", "src/006-A-pca/run.py")
    con = connect()
    taito = aoi.load("taito", con)
    tokyo = aoi.load("tokyo23", con)
    common = {
        "crs": "OGC:CRS84",
        "source": "study-geoai-algo-py original scripts and versioned data",
        "source_commit": COMMIT,
        "stop_on_overlap": True,
    }

    def outline(area):
        return json.loads(
            con.execute(
                "select st_asgeojson(st_geomfromtext(?))", [area.wkt]
            ).fetchone()[0]
        )

    chome_areas, taito_landmarks, taito_roads = _taito_context_and_landmarks(con, taito)
    ward_areas = _tokyo23_ward_context(con)
    taito_neighbor_wards = [
        w
        for w in ward_areas
        if w["name"] in {"台東区", "文京区", "荒川区", "墨田区", "千代田区", "中央区"}
    ]

    names, x, geometry, _ = original_a.load(con, taito)
    labels = KMeans(4, n_init=20, random_state=0).fit_predict(
        StandardScaler().fit_transform(x)
    )
    if len(names) != 108 or np.bincount(labels, minlength=4).tolist() != [
        24,
        65,
        4,
        15,
    ]:
        raise ValueError("town cluster counts differ from the pinned source report")

    town_cat_names = {
        "0": "飲食・商業",
        "1": "住宅の多い町",
        "2": "宿泊",
        "3": "文化・緑",
    }
    with (PROJECT / "outputs/taito-town-clusters.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "cluster",
                "name",
                "n_towns",
                *original_a.COLS,
                "examples",
            ]
        )
        for c in range(4):
            m = labels == c
            med = [round(float(v), 3) for v in np.median(x[m], axis=0)]
            ex = "・".join([n for n, keep in zip(names, m, strict=True) if keep][:5])
            writer.writerow([c, town_cat_names[str(c)], int(m.sum()), *med, ex])

    lodging_towns = [n for n, lab in zip(names, labels, strict=True) if int(lab) == 2]
    lodging_highlights = [
        {
            "id": town_name,
            "rank": str(idx),
            "label": f"{town_name} (宿泊)",
            "color": "#6A1B9A",
        }
        for idx, town_name in enumerate(lodging_towns, 1)
    ]

    draw(
        "taito-town-types",
        feature_collection(names, geometry, labels),
        common
        | {
            "question": "台東区の町丁目は、どのような型に分かれたか",
            "value": "value",
            "kind": "category",
            "unit": "町丁目",
            "expect_units": 108,
            "categories": town_cat_names,
            "method": "標準化した9特徴量の k-means、k=4、n_init=20、seed=0",
            "geometry_source": "国勢調査2020の町丁目境界 (estat-boundary-2020@823195c)",
            "data_version": (
                "国勢調査2020 / Overture 2026-09-23.1 / みちよみ e4966cdceff6 / "
                "OSM道路 e60e017f6a77"
            ),
            "outline": outline(taito),
            "context_areas": [
                {"name": "", "geometry": w["geometry"]} for w in taito_neighbor_wards
            ],
            "roads": taito_roads,
            "highlights": lodging_highlights,
            "landmarks": [
                lm
                for lm in taito_landmarks
                if lm["name"] not in {"日本堤", "清川"}
            ],
            "landmark_fontsize": 7.8,
        },
    )

    features.grid_profiles(con, tokyo).create_view("g")
    rows = con.execute(
        """
        select mesh, ln(1 + density), coverage, ln(1 + place_density), share_food,
               share_retail, share_lodging, share_culture, undergrounded_share,
               mean_green, ln(1 + cell_density), st_asgeojson(geometry),
               st_intersects(geometry, st_geomfromtext(?))
        from g order by mesh
        """,
        [taito.wkt],
    ).fetchall()
    ids = [str(row[0]) for row in rows]
    x = np.asarray([row[1:11] for row in rows], dtype=float)
    x = np.where(np.isnan(x), np.nanmedian(x, axis=0), x)
    z_grid = StandardScaler().fit_transform(x)
    labels = KMeans(original_c.K, n_init=20, random_state=0).fit_predict(z_grid)
    dpmm_fits = [
        original_d.dpmm(z_grid, seed, **original_d.CHOSEN) for seed in original_d.SEEDS
    ]
    best_dpmm = max(range(len(dpmm_fits)), key=lambda i: dpmm_fits[i].lower_bound_)
    dpmm_labels = dpmm_fits[best_dpmm].predict(z_grid)
    dpmm_kmeans_ari = round(float(adjusted_rand_score(dpmm_labels, labels)), 2)
    if len(ids) != 631 or np.bincount(labels, minlength=6).tolist() != [
        225,
        37,
        225,
        1,
        103,
        40,
    ]:
        raise ValueError("grid cluster counts differ from the pinned source report")

    outlier_id = next(
        mesh_id for mesh_id, lab in zip(ids, labels, strict=True) if int(lab) == 3
    )
    grid_cat_names = {
        "0": "都心寄りの混在地",
        "1": "人口・建物が少ない",
        "2": "住宅地",
        "3": "外れ値 (1格子)",
        "4": "無電柱化が多い",
        "5": "緑・文化",
    }
    in_taito = np.asarray([bool(row[12]) for row in rows], dtype=bool)
    grid_cols = [
        "ln_density",
        "coverage",
        "ln_place_density",
        "share_food",
        "share_retail",
        "share_lodging",
        "share_culture",
        "undergrounded_share",
        "mean_green",
        "ln_cell_density",
    ]
    with (PROJECT / "outputs/tokyo23-grid-clusters.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "cluster",
                "name",
                "n_cells",
                "n_taito_cells",
                *grid_cols,
            ]
        )
        for c in range(6):
            m = labels == c
            med = [round(float(v), 3) for v in np.median(x[m], axis=0)]
            writer.writerow(
                [
                    c,
                    grid_cat_names[str(c)],
                    int(m.sum()),
                    int((m & in_taito).sum()),
                    *med,
                ]
            )

    draw(
        "tokyo23-grid-types",
        feature_collection(ids, [row[11] for row in rows], labels),
        common
        | {
            "question": "東京23区の1km格子では、どの型がどこにあるか",
            "value": "value",
            "kind": "category",
            "unit": "格子",
            "expect_units": 631,
            "categories": grid_cat_names,
            "method": "標準化した10特徴量の k-means、k=6、n_init=20、seed=0",
            "geometry_source": "日本の標準地域メッシュ (3次メッシュ) / 区界 jp-admin c86cbe9f2200",
            "data_version": (
                "Overture 2026-09-23.1 / みちよみ e4966cdceff6 / "
                "WorldPop R2025A / OpenCelliD 2024-06-14"
            ),
            "outline": outline(tokyo),
            "context_areas": ward_areas,
            "context_fontsize": 7.5,
            "context_label_min_share": 0.002,
            "focus_areas": [
                {
                    "name": "台東区の境界 (18格子中15が混在地)",
                    "geometry": outline(taito),
                    "color": "#111111",
                    "linewidth": 2.2,
                }
            ],
            "highlights": [
                {
                    "id": outlier_id,
                    "rank": "1",
                    "label": f"外れ値格子 ({outlier_id}: 江東区臨海部、POI少数で宿泊20%)",
                    "color": "#8E2675",
                }
            ],
        },
    )

    features.street_cells(con, taito).create_view("sc")
    total_street_cells = int(
        con.sql(
            "select count(distinct cell_250m) from _sc where quarantined = 0"
        ).fetchone()[0]
    )
    rows = con.sql(
        f"select cell_250m, {', '.join(original_pc.COLS)}, "
        "st_asgeojson(geometry) from sc order by cell_250m"
    ).fetchall()
    ids = [str(row[0]) for row in rows]
    x = np.asarray([row[1:-1] for row in rows], dtype=float)
    x = np.where(np.isnan(x), np.nanmedian(x, axis=0), x)
    z = StandardScaler().fit_transform(x)
    pca = PCA().fit(z)
    scores = pca.transform(z)[:, 0]
    if len(ids) != 173 or not 0.40 < pca.explained_variance_ratio_[0] < 0.42:
        raise ValueError("street PCA differs from the pinned source report")

    min_idx = int(np.argmin(scores))
    max_idx = int(np.argmax(scores))
    ug_col = original_pc.COLS.index("undergrounded_share")
    wire_col = original_pc.COLS.index("wires_high_share")
    summary_metrics = {
        "dpmm_kmeans_ari": dpmm_kmeans_ari,
        "outlier_grid_mesh": outlier_id,
        "taito_street_total_cells": total_street_cells,
        "taito_street_min_scenes": 30,
        "taito_street_kept_cells": len(ids),
        "taito_street_excluded_cells": total_street_cells - len(ids),
        "taito_street_pc1_variance_ratio": round(
            float(pca.explained_variance_ratio_[0]), 3
        ),
        "taito_street_pc1_min": round(float(scores[min_idx]), 2),
        "taito_street_pc1_min_undergrounded_share": round(float(x[min_idx, ug_col]), 3),
        "taito_street_pc1_max": round(float(scores[max_idx]), 2),
        "taito_street_pc1_max_heavily_wired_share": round(
            float(x[max_idx, wire_col]), 3
        ),
    }
    (PROJECT / "outputs/summary-metrics.json").write_text(
        json.dumps(summary_metrics, ensure_ascii=False, indent=2) + "\n"
    )
    draw(
        "taito-street-pc1",
        feature_collection(ids, [row[-1] for row in rows], scores),
        common
        | {
            "question": "台東区の街路の違いは、どこに現れるか (PC1: 41%)",
            "value": "value",
            "kind": "diverging",
            "unit": "250m格子",
            "expect_units": 173,
            "negative": "無電柱化・緑・ブロック舗装",
            "positive": "電柱・電線",
            "method": "12特徴量を標準化した PCA の第1主成分",
            "geometry_source": "みちよみの cell_250m ID から復元した格子 / 町丁目境界 estat-boundary-2020",
            "data_version": "みちよみ e4966cdceff6 (撮影年1970〜2026) / OSM道路 e60e017f6a77",
            "outline": outline(taito),
            "context_areas": chome_areas,
            "context_linewidth": 0.35,
            "roads": taito_roads,
            "highlights": [
                {
                    "id": ids[min_idx],
                    "rank": "1",
                    "label": f"最小PC1 ({scores[min_idx]:.2f}: 上野公園、無電柱化86%)",
                    "color": "#0B556C",
                },
                {
                    "id": ids[max_idx],
                    "rank": "2",
                    "label": f"最大PC1 (+{scores[max_idx]:.2f}: 三筋・元浅草、電線多85%)",
                    "color": "#8E2675",
                },
            ],
            "landmarks": taito_landmarks,
            "landmark_fontsize": 7.8,
        },
    )


if __name__ == "__main__":
    main()

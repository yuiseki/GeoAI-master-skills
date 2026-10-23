"""Reproduce town-type maps from the pinned original analysis and its data readers.

Run from the repository root after cloning the source into this project's tmp/source.
The original code reads versioned public sources and caches them in /tmp/study-geoai.
"""

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
    from sklearn.preprocessing import StandardScaler
    from study_geoai import aoi, features
    from study_geoai.db import connect

    original_a = source_module("original_town_clusters", "src/005-A-k-means/run.py")
    original_c = source_module("original_grid_clusters", "src/005-C-grid-types/run.py")
    original_pc = source_module("original_street_pca", "src/006-A-pca/run.py")
    con = connect()
    taito = aoi.load("taito", con)
    tokyo = aoi.load("tokyo23", con)
    common = {
        "crs": "OGC:CRS84",
        "source": "study-geoai-algo-py original scripts and versioned data",
        "source_commit": COMMIT,
    }

    def outline(area):
        return json.loads(
            con.execute(
                "select st_asgeojson(st_geomfromtext(?))", [area.wkt]
            ).fetchone()[0]
        )

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
    draw(
        "taito-town-types",
        feature_collection(names, geometry, labels),
        common
        | {
            "question": "台東区の町丁目は、どのような型に分かれたか",
            "value": "value",
            "kind": "category",
            "unit": "町丁目",
            "categories": {
                "0": "飲食・商業",
                "1": "住宅の多い町",
                "2": "宿泊",
                "3": "文化・緑",
            },
            "method": "標準化した9特徴量の k-means、k=4、n_init=20、seed=0",
            "geometry_source": "国勢調査2020の町丁目境界",
            "data_version": (
                "国勢調査2020 / Overture 2026-09-23.1 / みちよみ e4966cdceff6"
            ),
            "outline": outline(taito),
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
    ids = [row[0] for row in rows]
    x = np.asarray([row[1:11] for row in rows], dtype=float)
    x = np.where(np.isnan(x), np.nanmedian(x, axis=0), x)
    labels = KMeans(original_c.K, n_init=20, random_state=0).fit_predict(
        StandardScaler().fit_transform(x)
    )
    if len(ids) != 631 or np.bincount(labels, minlength=6).tolist() != [
        225,
        37,
        225,
        1,
        103,
        40,
    ]:
        raise ValueError("grid cluster counts differ from the pinned source report")
    draw(
        "tokyo23-grid-types",
        feature_collection(ids, [row[11] for row in rows], labels),
        common
        | {
            "question": "東京23区の1km格子では、どの型がどこにあるか",
            "value": "value",
            "kind": "category",
            "unit": "格子",
            "categories": {
                "0": "都心寄りの混在地",
                "1": "人口・建物が少ない",
                "2": "住宅地",
                "3": "外れ値 (1格子)",
                "4": "無電柱化が多い",
                "5": "緑・文化",
            },
            "method": "標準化した10特徴量の k-means、k=6、n_init=20、seed=0",
            "geometry_source": "日本の標準地域メッシュ (3次メッシュ)",
            "data_version": (
                "Overture 2026-09-23.1 / みちよみ e4966cdceff6 / "
                "WorldPop R2025A / OpenCelliD 2024-06-14"
            ),
            "outline": outline(tokyo),
        },
    )

    features.street_cells(con, taito).create_view("sc")
    rows = con.sql(
        f"select cell_250m, {', '.join(original_pc.COLS)}, "
        "st_asgeojson(geometry) from sc order by cell_250m"
    ).fetchall()
    ids = [row[0] for row in rows]
    x = np.asarray([row[1:-1] for row in rows], dtype=float)
    x = np.where(np.isnan(x), np.nanmedian(x, axis=0), x)
    z = StandardScaler().fit_transform(x)
    pca = PCA().fit(z)
    scores = pca.transform(z)[:, 0]
    if len(ids) != 173 or not 0.40 < pca.explained_variance_ratio_[0] < 0.42:
        raise ValueError("street PCA differs from the pinned source report")
    draw(
        "taito-street-pc1",
        feature_collection(ids, [row[-1] for row in rows], scores),
        common
        | {
            "question": "台東区の街路の違いは、どこに現れるか (PC1: 41%)",
            "value": "value",
            "kind": "diverging",
            "unit": "250m格子",
            "negative": "無電柱化・緑・ブロック舗装",
            "positive": "電柱・電線",
            "method": "12特徴量を標準化した PCA の第1主成分",
            "geometry_source": "みちよみの cell_250m ID から復元した格子",
            "data_version": "みちよみ e4966cdceff6 / 撮影年 1970〜2026",
            "outline": outline(taito),
        },
    )


if __name__ == "__main__":
    main()

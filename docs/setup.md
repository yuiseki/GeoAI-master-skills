# 環境の準備

このリポジトリのコードを流すのに要るものは、`uv` だけ。Python のインストールも、ライブラリを入れる作業も要らない。

## uv を入れる

macOS と Linux:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

入ったら、新しい端末を開いて `uv --version` が動くかを確かめる。

## uvx の使い方

`uvx` は、必要なライブラリをその場で用意して、コマンドを動かす。

```sh
uvx --with numpy --with scikit-learn python script.py
```

`--with` に、スクリプトが使うライブラリを並べる。各スクリプトの先頭の説明に、どのライブラリが要るかが書いてある。初回はダウンロードで時間がかかり、2 回目以降は速い。

## DuckDB と SQL

データを読んで集計するのに、DuckDB を使う。SQL で書く。ファイルや URL を直接読めるので、読み込みの手順が要らない。

```sh
uvx --from 'duckdb>=1.5.5' python -c "
import duckdb
print(duckdb.sql(\"select count(*) from 'https://example.com/data.parquet'\"))"
```

DuckDB は 1.5.5 以上を使う。古い版は、空間の関数が壊れることがある。SQL は、次の 4 つが分かれば始められる。

| やりたいこと | SQL |
|---|---|
| 列を選ぶ | `select a, b from 'file.parquet'` |
| 行を絞る | `where year = 2022` |
| グループごとに数える、足す | `select region, count(*), avg(x) from ... group by region` |
| 2 つの表を結ぶ | `from t1 join t2 on t1.id = t2.id` |

空間の関数は `install spatial; load spatial` で使えるようになる。

## QGIS でやっていたことは、こう書く

| QGIS | このリポジトリ (DuckDB の SQL) |
|---|---|
| レイヤーを開く (shapefile、GeoJSON) | `select * from ST_Read('file.shp')`。Parquet は `select * from 'file.parquet'` |
| 属性テーブルを見る | `select * from ... limit 20` |
| 属性で選択 | `where 列 = 値` |
| 位置関係で結合 (join by location) | `join ... on ST_Within(点, 面)` や `ST_Intersects(a, b)` |
| 座標系を変える (再投影) | `ST_Transform(geom, 'OGC:CRS84', 'EPSG:6933', always_xy := true)` |
| 面積、距離を測る | 度のままでは測れない。投影してから `ST_Area`、`ST_Distance`。球面の距離は `ST_Distance_Sphere` (座標の順に注意、下) |
| バッファを作る | 投影してから `ST_Buffer(geom, メートル)` |
| 格子を作って数える | 投影した座標を `floor(x / 100000)` でセル番号にして `group by` |
| 結果を地図で見る | 結果を GeoJSON などに書き出して、QGIS で開いてよい。分析そのものは Python と SQL で書く |

座標の順の罠: 東京駅 (経度 139.77、緯度 35.68) から大阪駅 (経度 135.50、緯度 34.73) の距離は、約 402 km。DuckDB の `ST_Distance_Sphere` に `ST_Point(経度, 緯度)` のまま渡すと、481 km と黙って 2 割違う値が出る。この関数は、点の x を緯度として読む。既知の 2 点の距離と合うかを、必ず確かめる。詳しくは [.agents/skills/spatial-data-integration/references/duckdb-spatial.md](../.agents/skills/spatial-data-integration/references/duckdb-spatial.md)。

## 何も入れずに始める (Docker)

`uv` も Python も入れたくないときは、リポジトリ直下の `Dockerfile` で、道具の入った環境を作れる。入っているのは、Python 3.12、`uv`、DuckDB 1.5.5 以上 (空間拡張と httpfs は入れてある)、numpy、scipy、scikit-learn、pandas、pyarrow、statsmodels、networkx、shapely、rasterio、esda、libpysal、pyyaml、pytest。

```bash
docker build -t geoai-skills .
docker run --rm -it -v "$PWD":/work geoai-skills
```

- 手元のリポジトリを `/work` に見せるので、コンテナの中で作ったファイルは手元に残る。
- 中で `python .agents/skills/check_skills.py` と、各スキルの `scripts/` での `python -m pytest` が通ることを確かめてある。
- TabPFN、XGBoost、LightGBM、CatBoost は入れていない。使うときは `uvx --with tabpfn python ...` のように足す。
- ホストの利用者の番号が 1000 でないと、`/work` に書けないことがある。そのときは `--user "$(id -u):$(id -g)"` を付ける。

## 次に

[docs/tutorial/README.md](tutorial/README.md) のコードを、そのまま写して流す。

# beech-masting-satellite-proxy

東北 98 地点のブナの結実の評価 (地点 × 年、0〜3、1990〜2008 年) について、Landsat 5 TM の NDVI と NDMI の、その地点自身の平年からの偏差が、同じ年の中で「どの地点がより実るか」を当てる情報を持つかを確かめる。[beech-masting-spatial-proxy](../beech-masting-spatial-proxy/) では、地形と地点ごとの気象は年の中の地点の差をほとんど当てなかった。分け方 (A、B、C、50 km のブロック、15 km の緩衝帯、種) は前のプロジェクトと同じにして比べられるようにする。

計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行の記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。

## 置き場所

- `scripts/`: コードとテスト。
- `outputs/`: 報告が引く小さな表と図。
- `artifacts/beech-masting-satellite-proxy/`: 抽出の途中の大きな表 (git に入れない)。

## データ

- 目的変数: `yuiseki/fagus-crenata-masting-jp-2026-06` 版 db40a09 (Dryad、Masaki ほか、CC0)。東北 98 地点。北海道 4 地点の目的変数は、東北の判定が支持されたときだけ読む。
- 気温: 前のプロジェクトの `projects/beech-masting-spatial-proxy/outputs/site_year_climate.csv` (AgERA5 版 348e459 から作った地点 × 年の夏の気温の偏差) をそのまま読む。
- 衛星: `yuiseki/landsat5-fagus-crenata-sites-jp-2026-10` 版 939ee55 (Landsat 5 TM Collection 2 Level-2、USGS の public domain)。この研究のために凍結した。

## 再現

リポジトリの直下から。抽出 (1、2) は凍結した版を作る手順で、分析は 3 以降が凍結した版を読む。確認の段 (6) は計画どおり 1 回だけ流す。やり直すときは、出力を消す理由を記録に書いてから消す。

```sh
# 1. 抽出 (Planetary Computer。64 並列で約 2 時間。item ごとに保存し、途中から再開できる)
S=projects/beech-masting-satellite-proxy/scripts; A=artifacts/beech-masting-satellite-proxy
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR \
  uvx --from 'duckdb>=1.5.5' --with rasterio --with pyproj --with shapely --with pandas --with pyarrow python $S/landsat.py search $A
# 同じ uvx で: landsat.py pixels $A --workers 64、landsat.py table $A

# 2. Hugging Face への凍結と照合
uvx --with rasterio --with pandas --with pyarrow --with huggingface_hub python $S/publish_hf.py build $A
# 同じ uvx で: publish_hf.py upload $A、publish_hf.py verify $A 939ee55fa7ed45afc7b0a6cec83387c645622d3a

# 3. 被覆の監査 (目的変数を読まない)。規則は outputs/coverage_rule.json に固定済み
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy python $S/coverage.py 939ee55fa7ed45afc7b0a6cec83387c645622d3a projects/beech-masting-satellite-proxy/outputs

# 4. 季節の値
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy python $S/features.py projects/beech-masting-satellite-proxy/outputs

# 5. B2 開発期間と仕様の凍結 (仕様のファイルがあれば止まる)
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj python $S/run_dev.py projects/beech-masting-satellite-proxy/outputs

# 6. B3 確認期間を 1 回 (出力があれば止まる)、B4 反証 (400 回の並べ替えで約 1 時間)
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python $S/run_confirm.py projects/beech-masting-satellite-proxy/outputs $A
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python $S/run_falsify.py projects/beech-masting-satellite-proxy/outputs $A

# 7. 図
uvx --from 'duckdb>=1.5.5' --with matplotlib --with pandas python $S/plot.py projects/beech-masting-satellite-proxy/outputs

# テスト
cd $S && uvx --with numpy --with pandas --with pytest --with rasterio --with matplotlib python -m pytest -q
```

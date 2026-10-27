# tokyo-town-types

東京の地区を統計・POI・街路画像から類型化し、地域施策の対象を検討する前の下見に使えるかを検証した既存事例です。

- [整理したレポート](report.md)
- 移植元: [`study-geoai-algo-py/case-studies/004-town-types`](https://github.com/yuiseki/study-geoai-algo-py/tree/6880b32c097a7c65a6bd72a38682ce1dce1c9a2b/case-studies/004-town-types)
- 状態: 元コードの固定コミットを使い、町丁目の類型、1km格子の類型、街路PCAを再実行しました。元データの粒度別ファイルはこのリポジトリに複製していません。

`outputs/taito-town-types.png`、`tokyo23-grid-types.png`、`taito-street-pc1.png`、および各類型の特徴量中央値 (`outputs/taito-town-clusters.csv`、`outputs/tokyo23-grid-clusters.csv`) と要約指標 (`outputs/summary-metrics.json`) は、元コードが取得する版固定のデータから再生成できます。元コードは `tmp/source` に置きます (`tmp/` は Git 対象外)。初回はネットワーク接続と元データの取得が必要です。

```sh
cd projects/tokyo-town-types
git clone --filter=blob:none https://github.com/yuiseki/study-geoai-algo-py.git tmp/source
git -C tmp/source checkout 6880b32c097a7c65a6bd72a38682ce1dce1c9a2b
uv run --no-project --with 'duckdb==1.5.5' --with numpy --with matplotlib \
  --with scikit-learn --with rasterio --with pyarrow python scripts/reproduce_maps.py
```

既に `tmp/source` がある場合は clone を飛ばしてください。元コードの特徴量と分類設定を使用し、地図の描画は `.agents/skills/analysis-visualize/scripts/spatial_result_map.py` を使用します。元コードが利用する `/tmp/study-geoai/` のキャッシュは再利用できます。

シルエット係数の要約図は `outputs/source-values.csv` から再生成できます。

```sh
uv run --with matplotlib python scripts/plot.py
```

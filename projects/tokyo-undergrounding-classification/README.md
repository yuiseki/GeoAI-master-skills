# tokyo-undergrounding-classification

街路画像の特徴から無電柱化の有無を推定し、未整備道路の調査候補を絞れるか検証した既存事例です。

- [整理したレポート](report.md)
- 移植元: [`study-geoai-algo-py/case-studies/003-undergrounding`](https://github.com/yuiseki/study-geoai-algo-py/tree/6880b32c097a7c65a6bd72a38682ce1dce1c9a2b/case-studies/003-undergrounding)
- 状態: AUC は既存結果の整理。台東区の250m格子別シーン割合は、固定コミットの元コードと版固定データから再計算しました。

図は `outputs/source-values.csv` の値から再生成できます。

```sh
uv run --with matplotlib python scripts/plot.py
```

地図の再生成には、元コードを `projects/tokyo-town-types/tmp/source` に固定コミット `6880b32c097a7c65a6bd72a38682ce1dce1c9a2b` で配置し、次を実行します。初回はデータ取得にネットワークが必要です。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with numpy --with shapely \
  --with matplotlib --with scikit-learn --with rasterio --with pyarrow \
  python scripts/reproduce_map.py
```

中間 GeoParquet は `tmp/` に保存し、2通りの地図と来歴 JSON は `outputs/` に保存します。

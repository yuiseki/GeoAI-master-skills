# taito-shelter-planning

台東区で、住民への近さ、収容力、洪水リスクを同時に考えた拠点配置を検討した既存事例です。

- [整理したレポート](report.md)
- [意思決定上のトレードオフを論じた論文](paper.md)
- 移植元: [`study-geoai-algo-py/case-studies/002-shelter-planning`](https://github.com/yuiseki/study-geoai-algo-py/tree/6880b32c097a7c65a6bd72a38682ce1dce1c9a2b/case-studies/002-shelter-planning)
- 状態: 固定コミットの元コードで34個のパレート解を再計算し、国勢調査2020の町丁目人口密度を再検算・地図化しました。候補地点や個々の配置は複製していません。

図は `outputs/source-values.csv` の値から再生成できます。

```sh
uv run --with matplotlib python scripts/plot.py
```

人口密度地図は、元コードを `projects/tokyo-town-types/tmp/source` に固定コミット `6880b32c097a7c65a6bd72a38682ce1dce1c9a2b` で配置して再生成します。初回はデータ取得にネットワークが必要です。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with numpy --with shapely \
  --with matplotlib --with scikit-learn --with rasterio --with pyarrow \
  python scripts/reproduce_map.py
```

中間 GeoParquet は `tmp/`、地図と来歴 JSON は `outputs/` に保存します。

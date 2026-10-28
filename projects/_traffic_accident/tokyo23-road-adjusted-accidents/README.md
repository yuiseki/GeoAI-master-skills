# tokyo23-road-adjusted-accidents

[課題31の報告](report.md)。2025年東京23区の警察記録の人身事故を、2026年OSM道路中心線の延長と2020年国勢調査夜間人口で調整し、1kmメッシュの道路安全点検候補を探した探索分析です。

課題指定の固定版4データセットだけを使います。初回はHugging Faceの固定版Parquetから必要列を `tmp/` に取得します。`tmp/` はGitに含めません。全国版のOSM線データから23区周辺を切り出す段階が重く、再実行はキャッシュを使います。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy \
  python projects/_traffic_accident/tokyo23-road-adjusted-accidents/scripts/analyze.py
```

地図はリポジトリの `analysis-visualize` の塗り分けスクリプトで再生成します。主図は等間隔5階級、比較図は分位5階級です。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with numpy --with shapely --with matplotlib --with matplotlib-fontja \
  python .agents/skills/analysis-visualize/scripts/classify_map.py \
  projects/_traffic_accident/tokyo23-road-adjusted-accidents/tmp/map-units.parquet mesh surprise \
  --kind level --unit '-log10(NB2 upper-tail p)' --method equal --classes 5 \
  --compare quantile --palette cividis --crs 'JGD2011 3rd mesh (lon/lat)' \
  --source 'NPA 389500a / OSM 9a9b4a7 / census 6c486c8 / admin e6c87b1, 2026-10-24' \
  --no-labels --png projects/_traffic_accident/tokyo23-road-adjusted-accidents/outputs/accident-surprise-equal-map.png
```

分位図は `--method quantile --compare equal` と出力名 `outputs/accident-surprise-map.png` に替えます。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy --with pytest pytest -q \
  projects/_traffic_accident/tokyo23-road-adjusted-accidents/scripts/test_analyze.py
```

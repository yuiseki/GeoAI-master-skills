# tokyo23-accident-rate-2025

[課題30の報告](report.md)。東京23区の2025年発生の警察記録の人身事故を、2020年国勢調査の夜間人口と3次メッシュで照合した探索分析です。

使用するのは課題文に指定された固定版の `npa-traffic-accidents`、`estat-census-mesh-2020`、`jp-admin-2026-09` のみです。初回実行はHugging Face上の固定版Parquetに接続し、必要な列を `tmp/` にキャッシュします。キャッシュはGitに含めません。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy \
  python projects/tokyo23-accident-rate-2025/scripts/analyze.py
```

主順位の塗り分けはリポジトリの `analysis-visualize` で再生成します。図の階級・NoData・CRS・出典は同名のJSONに記録されます。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with numpy --with shapely --with matplotlib \
  python .agents/skills/analysis-visualize/scripts/classify_map.py \
  projects/tokyo23-accident-rate-2025/tmp/map-units.parquet mesh posterior_low \
  --kind rate --unit '人身事故件数/夜間人口1万人' --method quantile --classes 5 \
  --compare equal --palette cividis --crs 'JGD2011 3rd mesh (lon/lat)' \
  --source 'NPA 389500a / census 6c486c8 / admin e6c87b1, 2026-10-24' --no-labels \
  --png projects/tokyo23-accident-rate-2025/outputs/posterior-lower-map.png
```

等間隔版は `--method equal --compare quantile` と出力名 `outputs/posterior-lower-equal-map.png` に替えます。

```sh
uv run --no-project --with pytest --with scipy pytest -q \
  projects/tokyo23-accident-rate-2025/scripts/test_analysis.py
```

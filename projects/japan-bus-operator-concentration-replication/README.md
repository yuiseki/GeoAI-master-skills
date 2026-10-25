# 全国のバス停記録における事業者集中の追試

添付の「全国の徒歩圏バス停における事業者集中」と自治体別地図を、固定版データから独立したコードで追試した project。社会的な使い道は、交通供給の継続性について自治体や事業者へ追加確認する地域の選定である。記録された事業者名の集中と、運行の冗長性・撤退リスクは区別する。

- [計画](EXPERIMENT_PLAN.md): 既知の結果を読んだ後に固定した、探索的な再現性監査。
- [実行記録](EXPERIMENT_TRACKER.md): 実行と逸脱。
- [報告](report.md): 再現した結果、未追試の結果、解釈の限界。
- [監査値](outputs/audit.json)と[診断](outputs/diagnostics.json): 報告の数値の根拠。
- [自治体別CSV](outputs/municipalities.csv)と[地図](outputs/municipality-share.png): 自治体別の派生結果。

入力は `yuiseki/ksj-p11-bus-stop-jp@442223b4544103a922f21081c070dd5c69e4c23e`、`yuiseki/estat-census-mesh-2020@6c486c8649484e09e549c0c99b5fa89b4f416edb`、`yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135`。それぞれの原典・ライセンスは `dataset-discovery/references/` のカードを参照。人口は2020年、P11は2022年度版（資料の時点は事業者ごとに異なる）、境界の形は2020年で、時点は一致しない。

再現コマンド（リポジトリ直下から実行。実測環境は Python 3.13.3、DuckDB 2.0.0、NumPy 2.5.4、SciPy 1.18.1、Shapely 2.2.0、Matplotlib 3.11.2）:

```sh
uv run --no-project --with pytest --with numpy --with scipy python3 -m pytest -q projects/japan-bus-operator-concentration-replication/scripts/test_*.py
uv run --no-project --with duckdb --with numpy --with scipy --with shapely python3 projects/japan-bus-operator-concentration-replication/scripts/analysis.py
uv run --no-project --with numpy --with scipy python3 projects/japan-bus-operator-concentration-replication/scripts/diagnostics.py
uv run --no-project --with duckdb --with numpy --with scipy --with shapely --with matplotlib python3 projects/japan-bus-operator-concentration-replication/scripts/plot.py
```

`analysis.py` は全国のメッシュごとの結果を `artifacts/japan-bus-operator-concentration-replication/meshes.csv` に出す（大きいため Git 管理外）。`plot.py` は同じ `artifacts/` に行政界付きの一時的な GeoParquet を作り、リポジトリの `analysis-visualize/scripts/classify_map.py` を使う。小さい数値表、監査JSON、PNGは `outputs/` に置く。乱数は使わない。分類に使う距離は球面の大円距離で、徒歩経路距離ではない。

地図の階級件数は添付PNGと同じになった。ただし、このリポジトリの汎用地図スクリプトは全国の細かな自治体境界を黒線で描くため、地図単体の視認性は添付PNGのほうが高い。数値の正確な確認はCSVとJSONを優先する。

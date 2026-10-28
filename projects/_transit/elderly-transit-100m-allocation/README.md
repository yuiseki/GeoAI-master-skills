# 高齢者の交通空白メッシュ：1kmの年齢別人口を100mに配り直しても優先順位は残るか

[論文](paper.md)と[最終報告](report.md)、[実行記録](EXPERIMENT_TRACKER.md)、[事前計画](EXPERIMENT_PLAN.md)をご覧ください。結果は[配分・順位の要約](outputs/allocations-summary.json)、[診断](outputs/diagnostics.json)、[全メッシュの配分](artifacts/_transit/elderly-transit-100m-allocation/mesh-allocations.parquet)に保存しています。

## 何をしたか

東京都本土53市区町村の1kmメッシュで、65歳以上がバス停まで徒歩800m超かつ運行中駅まで1,500m超の場所に住む人数を、メッシュ内の人口配置だけを変えて4通りに配分した。中心点、5点等重み、100m WorldPop、1km一様。供給側（バス停・駅・徒歩道路・閾値）は4通りで固定した。上位10の重なりとSpearman順位相関、対象人数を比べた。

主な結果は、中心点と100m人口重みの上位10の重なりが2メッシュ、4配分すべてで上位10に残るのは八王子市 `53394207` の1メッシュだけ、中心点1位の品川区 `53393610` は100mで5位（1,839人→226.57人）、中心点4位の江戸川区 `53394648` は100mで33位（1,343人→69.57人）。配分を変えると優先順位は大きく入れ替わる。

## 再現

リポジトリのルートから。入力はHugging Face上の固定版データセットで、初回はOSMの切り出しとグラフ構築に時間・メモリがかかる。中間ファイルは `artifacts/_transit/elderly-transit-100m-allocation/` にキャッシュする。

```sh
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/build_inputs.py
python3 projects/_transit/elderly-transit-100m-allocation/scripts/read_worldpop.py
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/assign_worldpop.py
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/build_network.py
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/compute_allocations.py
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/diagnostics.py
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/spatial_checks.py
/tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/make_figures.py
python3 .agents/skills/research-paper-writing/scripts/check_paper.py projects/_transit/elderly-transit-100m-allocation/paper.md
python3 .agents/skills/analysis-reporting/scripts/check_report.py projects/_transit/elderly-transit-100m-allocation/report.md --level full --evidence projects/_transit/elderly-transit-100m-allocation/outputs/allocations-summary.json projects/_transit/elderly-transit-100m-allocation/outputs/diagnostics.json projects/_transit/elderly-transit-100m-allocation/outputs/paper-metrics.json projects/_transit/elderly-transit-100m-allocation/outputs/worldpop-assignment.json projects/_transit/elderly-transit-100m-allocation/outputs/input-accounting.json
```

`read_worldpop.py` はGDALを使うためシステムの `python3`、ほかは `/tmp/venv-geoai` の Python 3.12 を使った。環境が違う場合は、必要なパッケージ（duckdb、numpy、scipy、pandas、shapely、pyproj、pyarrow、matplotlib）を用意する。

## データ（固定版）

| 用途 | データセット | 版 |
|---|---|---|
| 2020年国勢調査 3次メッシュ（総人口・65歳以上・75歳以上） | `yuiseki/estat-census-mesh-2020` | `6c486c8649484e09e549c0c99b5fa89b4f416edb` |
| バス停（2022年度スナップショット） | `yuiseki/ksj-p11-bus-stop-jp` | `442223b4544103a922f21081c070dd5c69e4c23e` |
| 駅と運行状態（2026-07-31） | `yuiseki/ekidata-jp` | `a33321099406b47338be0d03a4887059473fde0c` |
| OSM道路（2026-08-31） | `yuiseki/osm-japan-src-2026-08` | `9a9b4a77e89e28a66bf15781644a16b63501f622` |
| 行政界（2026-09） | `yuiseki/jp-admin-2026-09` | `e6c87b1d7095c17422147962185071a986e13135` |
| WorldPop 100m 2020（R2025A、constrained） | `yuiseki/worldpop-jp-2026-01` の COG | `jpn_pop_2020_CN_100m_R2025A_v1.tif` |

## ファイル

- `scripts/build_inputs.py`: 53市区町村、1kmメッシュ、国勢調査、バス停、駅、道路の読み込み
- `scripts/read_worldpop.py`: WorldPop COGの窓読み
- `scripts/assign_worldpop.py`: 100m画素のメッシュ割り当てとNoData・0・範囲外の監査
- `scripts/build_network.py`: 徒歩グラフとバス停・駅への多始点Dijkstra
- `scripts/compute_allocations.py`: 4配分、閾値・年齢・スナップ・NoData・比の比較
- `scripts/diagnostics.py`: 上位10の重複、Spearman、分解、都県境感度、キーmesh
- `scripts/spatial_checks.py`: Queen隣接のMoran's I、市区町村別の差
- `scripts/make_figures.py`: 図1–4
- `outputs/`: 要約JSON、CSV、図PNGと図の来歴JSON
- `artifacts/_transit/elderly-transit-100m-allocation/`: 中間Parquet・ネットワーク・ログ

## 注意

- これは記述的な候補抽出で、介入の因果効果や個人の移動困難を推定していない。
- 人口は2020年、バス停は2022年度、駅・道路は2026年で時点が違う。
- WorldPopは国勢調査ではなく推計。メッシュ合計の比は中央値0.985だが、0.5未満73、2.0超85のメッシュがある。NoDataと未知の重みの扱いで上位は変わる。
- 標高・坂・階段の代替経路、バス便数、バリアフリー、実際の横断箇所は未確認。
- 5点の主結果は計画の文言（到達可能な点の平均）に戻した再計算。全点既知の保守的変種は探索として[実行記録](EXPERIMENT_TRACKER.md)に残した。

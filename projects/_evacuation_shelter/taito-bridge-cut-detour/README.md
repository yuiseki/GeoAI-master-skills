# taito-bridge-cut-detour

課題 hard-48 (避難所への経路冗長性と単一橋梁切断脆弱性) を、台東区に絞って試したもの。

問い: 台東区で、洪水に指定された緊急避難場所までの平常時の最短徒歩距離は短いのに、経路上の橋 1 つが使えなくなると避難距離が大きく伸びる (または届かなくなる) 500 m メッシュはどこか。その伸びは、川と線路のどちらを渡る橋で起きているか。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)
- 大きな生成物: `artifacts/_evacuation_shelter/taito-bridge-cut-detour/` (取り出した入力 `raw_b<緩衝帯>/`、出発点ごとの結果 `<variant>/origins.parquet`)

## データ (版を固定)

| データセット | 版 | 使ったもの |
|---|---|---|
| `yuiseki/gsi-evacuation-sites-jp` | `d8ad2169789b71c951e8808b2e54a953030aae07` | `sites` (指定緊急避難場所) のうち `flood` |
| `yuiseki/osm-japan-src-2026-08` | `9a9b4a77e89e28a66bf15781644a16b63501f622` | `planet_osm_line` の道、線路、水路。`planet_osm_polygon` の水面、建物、公園、霊園、動物園、線路の敷地 |
| `yuiseki/estat-census-mesh-2020` | `6c486c8649484e09e549c0c99b5fa89b4f416edb` | `T001140` (JGD2011) の 1 km メッシュの人口 (文脈として添えるだけ) |
| `yuiseki/jp-admin-2026-09` | `e6c87b1d7095c17422147962185071a986e13135` | 台東区 (`code5` 13106) の面 |

## 再実行

実データを読む実行は、メモリと CPU に上限を掛ける。

```sh
CAP="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
DEPS="--from duckdb>=1.5.5 --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas"

# テスト (合成のグラフ、答えが分かる例)
$CAP uvx --from pytest --with duckdb --with numpy --with scipy --with shapely --with pyproj --with pyarrow --with pandas \
  pytest -q scripts/test_cutdetour.py

# 避難場所の登録数 (23 区)
uvx --from 'duckdb>=1.5.5' python scripts/00_site_registration.py

# 入力の切り出し (緩衝帯 5 km が主。3 km と 8 km は頑健性)
for b in 5000 3000 8000; do $CAP uvx --from 'duckdb>=1.5.5' --with pyarrow python scripts/01_fetch.py --buffer-m $b; done

# 主と変種
for v in main cluster5 cluster20 sites_taito corridor buffer3000 buffer8000 tunnels all_rail all_river allways; do
  $CAP uvx $DEPS python scripts/02_run.py --variant $v
done

# 変種の比較 (B3、B4)、出発点の場所の印 (B6)、地図
uvx --with pandas --with numpy --with scipy python scripts/03_compare.py
$CAP uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pandas --with pyarrow python scripts/05_origin_context.py
$CAP uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pandas --with pyarrow --with matplotlib --with pyproj \
  python scripts/04_map.py

# 最短経路の木の道ごとの通過数と、ネットワークの図 (analysis-visualize の network_map.py)
$CAP uvx $DEPS python scripts/06_tree_edges.py
$CAP sh scripts/07_network_map.sh

# 報告の検査
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

## スクリプト

| スクリプト | すること |
|---|---|
| `scripts/cutdetour.py` | 線から歩行のグラフを作る、橋をまとめる、多始点の最短経路、構造物を 1 つずつ外した距離 |
| `scripts/test_cutdetour.py` | 合成のテスト。平行な線をまとめないと迂回が消えること、橋の上の節点に寄せた点が偽の「到達不能」になることなど |
| `scripts/00_site_registration.py` | 東京 23 区の、指定緊急避難場所の登録数を災害の種類ごとに数える |
| `scripts/01_fetch.py` | 台東区と緩衝帯の入力を凍結データから切り出し、行数を数える |
| `scripts/02_run.py` | 変種ごとに計算し、`outputs/<variant>/` に summary.json、cells.csv、structures.csv を書く |
| `scripts/03_compare.py` | 変種と主の比較 (上位 5 の重なり、順位相関)、川と線路の別の集計、主張の判定 |
| `scripts/04_map.py` | 主の結果の地図 (PNG) |
| `scripts/06_tree_edges.py` | 主の最短経路の木で、道ごとに経路が通る出発点を数える |
| `scripts/07_network_map.sh` | 上の表を、辺の色と太さで描く (黒と白の背景) |
| `scripts/05_origin_context.py` | 出発点が公園、霊園、動物園、線路の敷地にあるか、建物の近くか (探索) |

出典: 国土地理院ウェブサイト (指定緊急避難場所データ)、© OpenStreetMap contributors (ODbL 1.0)、「令和2年国勢調査」(総務省統計局)。いずれも加工して作成。

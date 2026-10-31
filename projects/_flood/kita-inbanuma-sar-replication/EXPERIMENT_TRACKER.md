# 記録: 北印旛沼の浸水を Sentinel-1 で検知した note 記事の追試

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 取得と格子 | sentinel-1-rtc (S1C 2026-09-12、2026-09-24、軌道 39)、DEM5A z15 651 枚と DEM10B z14 176 枚 (2026-10-31 取得)、WorldCover 2021 v200、gsi-inundation-estimate-kita-inbanuma-jp-2026-10@e760fba | done | outputs/grid_summary.json | - | 格子 1,700 × 2,700 (EPSG:32654、10 m)。SAR と標高の欠測 0。DEM10B で埋めた画素 321,753。9/24 の輪郭線を塗った面積 4.9391 km² |
| R002 | B1〜B5 | A1〜A5 | main | 計画の手順と判定 | R001 と同じ | done | outputs/blocks.json、outputs/detect_fit.json | - | 比較範囲は輪郭線を 1,101.4 m 広げた 38.0 km²。A2 と A4 は再現、A1 (0.892)、A3 (検出率 +0.033)、A5 (面積の比 1.09) は再現しない。水の分布は −18.593 dB (標準偏差 5.959)、VH の閾値 −6.105 dB |
| R003 | 頑健性 | A1〜A5 | main | 計画の頑健性 7 つと外接矩形の範囲 | R001 と同じ | done | outputs/blocks.json の variants | - | 閾値 0.3 で A1 は再現側 (0.919)。塊の最小 25 画素と地形の範囲なしは判定の面積が 38.7 km² 前後に膨らむ。A3 はどの設定でも再現しない |
| R004 | B3 (探索) | A3 | exploratory | 見逃しの内訳、記事 2 の水位 (上位 1 %)、記事の閾値 −3.3 dB | R001 と同じ | done | outputs/explore_a3.json | 結果の後に足した | 見逃し 19,170 画素のうち、範囲の外 12,834、範囲の中で VH が閾値以下 1,637。水位を上位 1 % にし閾値を −3.3 dB にすると検出率 0.807、適合率 0.422 |
| R005 | 図 | A1〜A3 | - | 前後の合成、判定と推定図の比較 | R002 | done | outputs/composite.png、outputs/compare.png | - | 推定図に無い判定の多くは、沼の南東の岸の帯 (WorldCover で水域でない) |

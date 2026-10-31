# 記録: 北印旛沼の浸水を Sentinel-1 で検知した note 記事の追試

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 取得と格子 | sentinel-1-rtc (S1C 2026-09-12、2026-09-24、軌道 39)、DEM5A z15 651 枚と DEM10B z14 176 枚 (2026-10-31 取得)、WorldCover 2021 v200、gsi-inundation-estimate-kita-inbanuma-jp-2026-10@e760fba | done | outputs/grid_summary.json | - | 格子 1,700 × 2,700 (EPSG:32654、10 m)。SAR と標高の欠測 0。DEM10B で埋めた画素 321,753。9/24 の輪郭線を塗った面積 4.9391 km² |
| R002 | B1〜B5 | A1〜A5 | main | 計画の手順と判定 | R001 と同じ | done | outputs/blocks.json、outputs/detect_fit.json | - | 比較範囲は輪郭線を 1,101.4 m 広げた 38.0 km²。A2 と A4 は再現、A1 (0.892)、A3 (検出率 +0.033)、A5 (面積の比 1.09) は再現しない。水の分布は −18.593 dB (標準偏差 5.959)、VH の閾値 −6.105 dB |
| R003 | 頑健性 | A1〜A5 | main | 計画の頑健性 7 つと外接矩形の範囲 | R001 と同じ | done | outputs/blocks.json の variants | - | 閾値 0.3 で A1 は再現側 (0.919)。塊の最小 25 画素と地形の範囲なしは判定の面積が 38.7 km² 前後に膨らむ。A3 はどの設定でも再現しない |
| R004 | B3 (探索) | A3 | exploratory | 見逃しの内訳、記事 2 の水位 (上位 1 %)、記事の閾値 −3.3 dB | R001 と同じ | done | outputs/explore_a3.json | 結果の後に足した | 見逃し 19,170 画素のうち、範囲の外 12,834、範囲の中で VH が閾値以下 1,637。水位を上位 1 % にし閾値を −3.3 dB にすると検出率 0.807、適合率 0.422 |
| R005 | 図 | A1〜A3 | - | 前後の合成、判定と推定図の比較 | R002 | done | outputs/composite.png、outputs/compare.png | - | 推定図に無い判定の多くは、沼の南東の岸の帯 (WorldCover で水域でない) |
| R006 | sanity (段 B) | - | - | 取得、推定図の深さ | 推定図の深さのタイル z16 (4 版、各 374 枚)、PDF 4 枚の凡例、GRD 5 枚 (軌道 39: 9/12、9/24、10/06。軌道 141: 9/19、10/01)、RTC 軌道 141 の 2 枚。2026-10-31 取得 | done | outputs/gsi_depth.json、outputs/legend_0924.csv | 凡例の帯の切り出しを直した (マスクが帯の周りの影を含んでいた)。結果の前 | 凡例は 4 版で同じ。凡例から遠い色は 0 画素 (距離 5 では 9/22 に 5 画素)。輪郭線の中で深さのある画素 96.9〜98.8 % |
| R007 | GRD の検査 | - | - | 自分の GRD の処理 | R006 と同じ | done | outputs/grd_check.json | 検査の基準を WorldCover の水域に替えた (計画の変更)。対応表の内挿を計画どおり線形にした。DEM に EGM96 のジオイド高 (34.589〜37.004 m) を足した | 5 枚とも WorldCover に対し 0.55 画素以内。RTC 版は軌道 39 で行 −1.8、列 1.7〜2.5、軌道 141 で行 −2.2、列 −0.8 画素ずれる |
| R008 | E1〜E7 | D1〜D7 | main | 計画 (変更後) の手順と判定 | R006 と同じ | done | outputs/blocks_b.json、outputs/water_b.json | - | D3 だけ再現。9/24 の船形干拓の水面が 5.8 m (推定図からの内挿 2.234 m)。推定図の水面は記事より 0.166〜0.194 m 高い |
| R009 | 頑健性 (段 B) | D1〜D7 | main | RTC の水、VV だけの水、95 % 点、IoU、色の距離 5 | R006 と同じ | done | outputs/blocks_b.json の variants | - | 95 % 点と IoU では D3 と D4 が再現。9/24 の水面は 1.666 m、1.494 m |
| R010 | E1、E2 (探索) | D1、D2、D4 | exploratory | 水面を押し上げた画素の内訳、DEM5A の値がある所だけ | R006 と同じ | done | outputs/explore_b.json | 結果の後に足した | 推定図の水面より高い 226 画素のうち 223 が DEM10B で埋めた所。DEM5A だけでは水面 1.758 m、偏り −0.604 m、D3 と D4 が再現 |
| R011 | B1〜B5 (探索) | A1〜A5 | exploratory | 段 A を自分の GRD で | R006 と同じ | done | outputs/blocks_a_grd.json | 結果の後に足した | A1 (94.6 %)、A2、A4 が再現、A3 と A5 は再現しない |
| R012 | 図 (段 B) | D2、D3、D5 | - | 水面の推移、深さの帯、9/24 の深さ | R008、R010 | done | outputs/polder_surface.png、outputs/depth_0924.png | - | - |

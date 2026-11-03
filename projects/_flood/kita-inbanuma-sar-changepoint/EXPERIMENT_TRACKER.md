# 記録: 北印旛沼の Sentinel-1 時系列で、画素ごとの変化点を当てる

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 模擬 | scripts/test_cp.py | done | scripts/test_cp.py | - | 17 件通過。最初は「単偏波でカイ二乗近似が甘い」と読んだが誤りで、日ごとの誤警報の膨らみ (約 1.3 α) は、誤警報の後に基準が極端な 1 枚から作り直されるため (誤警報が対で出る)。近似と正確なベータの帰無分布は 0.1 ポイント以内で一致。計画の前 |
| R002 | sanity | - | - | 取得と格子 | sentinel-1-rtc の S1C、軌道 39 の 17 枚と軌道 141 の 20 枚 (2026-11-03 取得)、DEM5A z15 551 枚、DEM10B z14 150 枚、WorldCover 2021 v200、gsi-inundation-estimate-kita-inbanuma-jp-2026-10@e760fba | done | outputs/grid_summary.json | - | 格子 1,700 × 2,700 (EPSG:32654、10 m)。37 枚とも同じ格子。SAR の欠測 0。9/24 の輪郭線を塗った面積 4.9391 km² (兄弟のプロジェクトと同じ) |
| R003 | sanity | - | - | 生のデータの性質 | R002 と同じ | done | outputs/quality.json | 隣の画素の相関の出し方を直した (区画ごとの平均を引く)。変化の検定の前 | 時系列の中央値に対する位置のずれは全ての日で 0.05 画素以下。ENL の決め方 (比から逆算した L の中央値、70 個) は 6.4。区画の中の ENL は 4〜6 月に 2〜3 まで下がる (水田の湛水と生育)。隣の画素の ln 比の相関は 0.64〜0.77 で、区画の分散から出した ENL は大きめに出ている可能性がある (検定が甘くなる向き)。計画どおり 6.4 を使い、0.75 倍の版と B0 で見る |
| R004 | B0〜B4 | C0〜C4 | confirmatory | 主分析 (α 0.01、ENL 6.4、VV と VH、3 月から) | R002 と同じ | done | outputs/blocks.json、outputs/daily_o39.csv、outputs/daily_o141.csv | - | C0 は退ける (林の誤警報の比 2.309、2.532)。C1 は支持 (0.682 対 0.0582)。C2 は支持 (0.6297 対 0.0429、10/01 が 0.6232、9/19 が 0.0126)。C3 は支持 (0.8532、農地の参考 0.5126)。C4 は退ける (差 0.0199、閾値 6.54 dB) |
| R005 | 頑健性 | C0〜C3 | confirmatory | α 2 段、ENL 2 段、VV だけ、7 月から、境界の除外 | R002 と同じ | done | outputs/blocks.json の variants、edge_excluded | - | C1〜C3 は全ての設定で支持。C0 は ENL 0.75 倍 (4.8) で 0.913、1.002 と模擬に合い、α 0.05 と VV だけ (軌道 39)、7 月から (軌道 39) でも 2 以下 |
| R006 | 図 | - | - | 変化点の撮影日の地図、日ごとの割合 | R004 | done | outputs/changepoint_map.png、outputs/daily_share.png | - | 沼の南の岸の帯は 10/30 まで戻らない (推定図の輪郭線の外) |
| R007 | B2 (探索) | C2 | exploratory | 9/24 の輪郭線のうち 10/01 までに引いた所の、軌道 141 の 9/19 | R004 | done | outputs/daily_o141.csv | 結果の後に見た | 9/19 に暗くなった割合 0.01858、農地 0.02353。この所も 9/19 には浸水していなかったと読める (探索) |

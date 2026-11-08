# 記録: 局所の時間雨量と床上浸水の割合、気象庁の見落とし

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 調査単位 | tokyo-flood-record-jp@354b0d9、jma-rain-tokyo@4391f76 (tokyo23-flood-record-vs-a31a の 01_fetch.py) | done | outputs/units_summary.json | - | 5,845 行、日付のある調査単位 2,052 (日付の無い 197 を除く)、雨量の読める単位 1,933、災害日 129。23 区の内水は前半 1,048、後半 280。nro_flag 0 の雨量計の事象 393、そのうち 50 mm/h 以上 119 |
| R002 | B1〜B3 | C1〜C3 | main | 計画の規則 | R001 と同じ | done | outputs/blocks.json | - | C1 支持 (差 0.21 [0.02, 0.33]、前半 0.002、後半 0.085、1 日抜きの最小 0.13)。C2 支持 (0.29 [0.09, 0.48]、後半 0.03)。C3 判定できない (0.14 [−0.01, 0.28]) |
| R003 | B1、B2 (探索) | C1、C2 | exploratory | 期間の中の差と、期間をそろえた差 | R001 と同じ | done | outputs/within_period.json | 結果の後に足した | B1 前半 0.002 [−0.10, 0.11]、後半 0.085 [0.017, 0.21]、そろえた差 0.047 [−0.02, 0.15]。B2 前半 0.31 [0.10, 0.49]、後半 0.03 [−0.03, 0.13] |
| R004 | 図 | C1 | - | 帯ごとの床上の割合 | R002 | done | outputs/overfloor_by_band.png | - | 前半は平ら、後半は全体に高い |
| R005 | B1、B2 (探索) | C1、C2 | exploratory | 03_within_period.py の修正 (2026-11-09) | R001 と同じ (入力を Hugging Face の同じ版から取り直し、units_summary.json と within_period.json が以前と同じバイトで再現することを確かめた) | done | outputs/within_period.json | 足したテストで見つかったバグの修正 | 期間をそろえた差で、重みが 0 の期間 (境の上の単位が無い期間) の差が NaN になり、NaN × 0 で全体が NaN になっていた。日を引き直した 2,000 回のうち、B1 は 0 回、B2 は 736 回が NaN で、区間から黙って落ちていた。直した後、B2 のそろえた差の 90% 区間は [0.099, 0.499] から [0.103, 0.499] に変わった。報告と記録に書いた数字 (B1 のそろえた差、B2 の前半と後半) は変わらない |

# 記録: 台東区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | - | 東京の本票 205,541 行、台東区 4,517 行。コードと面の照合: 両方 4,464、コードだけ 53、面だけ 12 |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2025 年の区間 617〜720 件は 2019 年の 664〜769 件と重なる。規則により減ったと書かない |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 交差点内 45.9% (4 位)、生活道路 狭い読み 14.5% (21 位)、広い読み 25.6% (20 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 若い歩行者と自転車は 17 時台が最多 (45 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 28 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | 1 回目の結果を見た後、地点の名前に首都高速の名前が出たため、名付けから motorway を除いた。前半と後半を年平均 (3 年と 4 年で割る) にした。地点の選び方と半径は変えていない | 20 m で 12/15、50 m で 9/15 が 30 m 以内に残る |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | 階級は classify_map.py で決めたが、出力の地図は経度・緯度のまま縦横比が歪み、凡例が地図に重なったため、同じ区切りで plot.py で EPSG:6677 に描き直した | 分位と等間隔で 77.8% の町丁の色が変わる |
| R008 | - | - | done | outputs/deaths.csv | 1 回目の後、亡くなった人の種別 (人身損傷程度) を足した | 16 件のうち歩行者 11 人 |

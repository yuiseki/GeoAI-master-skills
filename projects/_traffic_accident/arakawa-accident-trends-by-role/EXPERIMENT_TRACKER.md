# 記録: 荒川区の交通事故の傾向 (ロール別レポート)

台東区の型 (台東区の記録の R010〜R015 で直した版、2026-11-03) を写して流した。台東区の R010〜R015 で足された検査と読み方 (区コードでの順位、KEY_CODE でまとめる町丁、水面と名前の無い単位、閉校した学校、首都高速を除いた地点、道路の短い町丁、年ごとのコードと面の件数) は、1 回目から入っている。

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の検査値 `TOWN_COUNT`、`TOWN_UNITS`、`TOWN_POPULATION` を 0 で 1 回流して止め、出た値 (52 行、52 単位、217,475 人) を書いた。東京の本票と 23 区は用意された 2 ファイルを使った (205,541 行、ファイルの年 7 つの検査は通った) | 荒川区 2,322 行、位置の無い行 0。コードと面の照合: 両方 2,310、コードだけ 12、面だけ 43。年ごとのコードと面の件数は analysis.json の `by_year_coded_vs_inside`。学校 35 校 (「旧」で始まる名前を除いた後)。水面調査区、名前の無い単位、まとめた町丁、道路の無い町丁、道路が 0.5 km より短い町丁は、どれも 0 |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 指数 (2019 年=100) は 2020 年 88.8、2021 年 83.9、2025 年 99.1。どの年の区間も 2019 年の区間 (312.4〜386.6 件) と重なる。規則により増えた、減ったと書かない |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 自転車 61.8% (1 位)、生活道路 狭い読み 36.8% (3 位)、広い読み 49.8% (1 位)、高齢の歩行者 5.1% (3 位)、夜 26.2% (23 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全ては 17 時台が最多 (184 件)。若い歩行者と自転車は 16 時台と 17 時台 (34 件ずつ) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 35 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 上位 15 は 12〜25 件。20 m で 11/15、50 m で 11/15 が 30 m 以内に残る。首都高速の事故は区に 0 件で、首都高速を除いた 30 m の地点は 15/15 が同じ |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | - | 道路あたりの上位 5 は全て南千住 (一、四、六、七、八丁目)。分位と等間隔で 59.6%、分位と Jenks で 57.7% の町丁の色が変わる。町丁の外の 12 件は入らない |
| R008 | - | - | done | outputs/deaths.csv, outputs/summary.txt | - | 死亡事故 9 件、亡くなった人は歩行者 5、自転車 3、二輪車 1 |
| R009 | B4, B5, B6 | exploratory | done | outputs/school-map.json, outputs/hotspots-map.json, outputs/town-rate.json | 図を見た後に、plot.py の地名の位置と番号の位置を決めた (値と選び方は変えていない)。1 回目は、学校の地図で町屋、東尾久、西日暮里の地名が学校の四角 (第五峡田小、尾久小、第一日暮里小) を隠し、地点の地図で 13 の番号が 11 の番号と 11 の円に重なった。`LANDMARK_OFFSETS` で 3 つの地名をずらし、`NUMBER_OFFSETS` で 13 を円の左下に移した | 2 回目は 3 枚とも text_overlaps 0 件。拡大図は南千住の日光街道 (1、2、3、4、6、8、10、14 位)。全部の PNG を目で確かめた |

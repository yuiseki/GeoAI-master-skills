# 記録: 練馬区の交通事故の傾向 (ロール別レポート)

台東区の型 (記録の R001〜R019 を直した 2026-11-03 の版) を写して流した。区に固有の定数のほかは、スクリプトを変えていない。

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の町丁の検査値を 0 にして 1 回目を流して止め、出た値 (境界ファイル 202 行、KEY_CODE で 202 単位、752,608 人) を `TOWN_COUNT`、`TOWN_UNITS`、`TOWN_POPULATION` に書いた。東京の本票と 23 区の面は、用意された 2 ファイルを使い、行数と年の数の検査を通した | 東京の本票 205,541 行、練馬区 7,407 行、位置の無い行 0。コードと面の照合: 両方 7,335、コードだけ 72、面だけ 14。学校 101 校、閉校した学校 2 校 (旧・光が丘第七小学校、旧国立東京学芸大学附属大泉中学校) を除いた。道路の無い町丁は西大泉町 (事故 0 件)。水面調査区と、まとめた町丁は無い |
| R002 | B1 | exploratory | done | outputs/yearly.csv | 1 回目の地点を見た後、路線の区分「その他」の中身と 1 位の地点の路線を、`tmp/check_other_routes.py` で数えた (型には入れていない。出力は tmp/other_routes.csv)。計画で見込んだとおり、関越自動車道と東京外環自動車道とみられる `路線コード` 4000 番台が「その他」に入っていた | 2022 年の区間 891.5〜1,013.4 件は 2019 年の 1,147.6〜1,285.3 件と重ならない。2025 年の区間 1,056.3〜1,188.6 件は 2019 年と重なるので、規則により減ったと書かない。自転車の単独を除くと 2025 年の指数は 92.3 から 81.1 |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 交差点内 46.4% (3 位)、生活道路 狭い読み 30.1% (9 位)、広い読み 44.4% (7 位)、若い歩行者と自転車 13.3% (7 位)、夜 27.2% (21 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全体は 8 時台 (618 件) が最多。若い歩行者と自転車は 16 時台 (123 件) と 8 時台 (115 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 101 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | 拡大図の範囲 (谷原・高松・大泉町・高野台)、地名、番号の位置は、地点の結果を見てから決めた (図の調整で、値と選び方は変えていない) | 20 m で 11/15、50 m で 10/15 が 30 m 以内に残る。首都高速の事故は 0 件で、除いた読み方は主の読み方と同じ 15 地点。1 位 (37 件) は交差点内 0 件、路線は全て「その他」、30 m 以内に名前のある一般の道が無い。tmp/other_routes.csv では 37 件が全て `路線コード` 4107、4108、4201 (高速自動車国道とみられる) |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json, outputs/town-rate.json | - | 分位と等間隔で 79.1% の町丁の色が変わる。道路 0.5 km 未満の町丁は無い。上位 5 のうち 3 つが光が丘 |
| R008 | - | - | done | outputs/deaths.csv | - | 死者のある事故 49 件 (死者 50 人)。亡くなった人は自転車 20、歩行者 14、二輪車 10 |
| R009 | B4, B5, B6 | exploratory | done | outputs/school-map.json, outputs/hotspots-map.json, outputs/town-rate.json | 1 回目の text_overlaps は学校の地図で 5 件 (中村、北町、土支田、南大泉、大泉学園町の地名が学校の四角を隠した)、地点の地図で 2 件 (番号 4 と 7、6 と 10 が重なった)。`LANDMARK_OFFSETS` で 5 つの地名をずらし、`NUMBER_OFFSETS` で 4 と 6 を円の左上、7 と 10 を円の下に移した | 3 枚とも text_overlaps 0 件。全ての PNG を開いて目で確かめた |
| R010 | B5, B6 | exploratory | done | outputs/route_class.csv, outputs/analysis.json, outputs/hotspots.csv, outputs/towns.csv, outputs/hotspot-halves.png | 台東区の型の R020 (2026-11-03、練馬区と杉並区の報告から) を写して全部を流し直した。結果を見た後の変更。`路線コード` 4000〜4999 を「高速自動車国道」の区分にし、高速道路を除く読み方と hotspots.csv と towns.csv の `expressway` を 4000〜5499 にした。analysis.json に `other_route_codes` を出し、前半と後半の図の印を [高速道路 n/件] にした。練馬区の定数と地名の調整は変えていない | 高速道路の事故 122 件 (高速自動車国道 122、首都高速 0)。「その他」は 322 件から 200 件 (9500 が 110、9900 が 78)。上位 15 の円に高速道路 37 件 (全て 1 位)、除くと 30 m の上位 15 のうち 14 地点が残る (R006 では 15)。towns.csv の expressway の合計は 120 件。地点の選び方、順位、町丁の上位 5 は前と同じ。text_overlaps は 3 枚とも 0 件 |

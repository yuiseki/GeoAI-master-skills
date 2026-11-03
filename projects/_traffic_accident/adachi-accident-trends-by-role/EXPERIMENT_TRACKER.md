# 記録: 足立区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の検査値 `TOWN_COUNT`、`TOWN_UNITS`、`TOWN_POPULATION` を 0 で流して止め、出た値 (268 行、268 単位、695,043 人) を書いた (2026-11-03)。東京の本票と 23 区は用意された 2 ファイル (md5 3dcf22ae…、cba05bb5…) を使い、行数と年の数の検査を通した | 東京の本票 205,541 行、足立区 12,169 行。コードと面の照合: 両方 12,153、コードだけ 16、面だけ 18。年ごとのコードと面の件数の差は 2 件以内。学校 100 校、道路 10,111 本 |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2025 年の区間 1,540〜1,699 件は 2019 年の 1,710〜1,877 件と重ならない。規則により、2025 年は 2019 年より減ったと書ける。2023 年 (1,837〜2,010 件) は 2019 年と重なる |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 歩行者 12.5% (23 位)、自転車 49.1% (7 位)、若い歩行者・自転車 13.9% (6 位)、生活道路 狭い読み 29.7% (11 位)、広い読み 43.8% (8 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 若い歩行者と自転車は 16 時台が最多 (205 件)、平日に限ると 8 時台 (178 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 100 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 20 m で 8/15、50 m で 8/15 が 30 m 以内に残る。規則により地点の順位を断定しない。首都高速の事故は 191 件、上位 15 の円には 0 件で、除いても 15 地点が残る |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | - | 分位と等間隔で 78.3% の町丁の色が変わる。道路の無い町丁は西伊興町 (0 件) の 1 つ。道路 0.5 km 未満で上位 5 に数えないのは入谷町，舎人町 (3.318) と古千谷二丁目 (1.288) で、どちらも 5 位 (4.588) より下なので上位 5 は変わらない |
| R008 | B5, B6 | exploratory | done | outputs/hotspots-map.json, outputs/school-map.json, outputs/town-rate.json | 1 回目の図を見た後、地名と番号の位置だけを直した (値と選び方は変えていない)。学校の地図で北千住、西新井、竹の塚、綾瀬の地名が学校の四角を隠したので `LANDMARK_OFFSETS` で動かした。全体の地点の図で環七の 14、9、10 位の番号が 1 つの文字列に見えたので `NUMBER_OFFSETS` で離した。町丁の地図では北千住が 3 位の番号に重なるので `TOWN_MAP_SKIP` に入れた | 文字の重なりは 3 枚とも 0 件 |
| R009 | B5, B6 | exploratory | done | outputs/analysis.json, outputs/hotspots.csv, outputs/towns.csv | 写した後に台東区の型が R013、R014 で直されたので (2026-11-03、足立区の結果を 1 回見た後)、スクリプトを写し直して全部を流し直した。道路 0.5 km 未満の町丁を上位 5 に数えない規則、同じ名前の単位、地点の選び方の省メモリ化、拡大図の番号がほかの円を隠すのを数える検査が入った。足立区の定数は変えていない | 地点、町丁の上位 5、図の重なりの数は写し直す前と同じ。町丁の上位 5 は道路の下限で変わらない |

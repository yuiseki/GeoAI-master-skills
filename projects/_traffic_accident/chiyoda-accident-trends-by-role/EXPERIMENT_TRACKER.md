# 記録: 千代田区の交通事故の傾向 (ロール別レポート)

台東区の型 (2026-11-03 の版、記録 R001〜R020 の直しを含む) を写して、全部を作り直した (2026-11-03)。古い版 (台東区の古い版を写したもの) のスクリプト、報告、出力は、同じ名前のファイルを新しい版で上書きした。古い版にあって型に無いファイルは無かった。

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の検査値は 1 回目に 0 で流して止め、出た値を書いた: `TOWN_COUNT` 116、`TOWN_UNITS` 115、`TOWN_POPULATION` 66,680。東京の本票と 23 区の面は用意されたファイルを使った (md5 3dcf22ae…、cba05bb5…、行数と年の数の検査は通った) | 東京の本票 205,541 行、千代田区 4,232 行。コードと面の照合: 両方 4,197、コードだけ 35、面だけ 30。年ごとのコードと面の件数に跳ねは無い (`by_year_coded_vs_inside`)。神田紺屋町が境界ファイルの 2 行で、まとめて 115 単位。水面調査区、名前の無い単位、閉校した学校は無い |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2025 年の区間 547.2〜643.7 件は 2019 年の 609.6〜711.3 件と重なる。規則により減ったと書かない。2020 年の指数 75.7 (23 区 83.7) |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 自転車 27.3%、若い歩行者・自転車 5.7%、生活道路 狭い読み 9.3% と広い読み 17.3% がどれも 23 区で 23 位。夜 36.1% は 4 位。住民千人あたり 9.07 件/年は 1 位 (参考値) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全体と若い歩行者・自転車の両方で 17 時台が最多 (315 件、23 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 11 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 20 m で 12/15、50 m で 10/15、高速道路を除いた 30 m で 14/15 が 30 m 以内に残る。上位 15 のうち 8 が靖国通りの九段下〜須田町。高速道路の事故は 251 件で、上位 15 の円には 14 位の 3 件だけ |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | - | 分位と等間隔で 78.1% の町丁の色が変わる。町丁「千代田」(皇居) は道路が 0 km で値なし (事故 1 件)。道路 0.5 km 未満で 5 位の値を超えるのは神田西福田町 (0.132 km、8 件) だけで、上位 5 に数えない |
| R008 | - | - | done | outputs/deaths.csv | - | 24 件のうち亡くなったのは歩行者 11 人 (65 歳以上 7 人)、二輪車 7 人 |
| R009 | B4, B5, B6 | exploratory | done | outputs/hotspots-map.json, outputs/school-map.json, outputs/town-rate.json | plot.py の千代田区の定数 (地名、拡大の範囲、地名の位置) は図を描いて決めた。1 回目は神保町が 5 位の円を、霞が関が 14 位の円と番号 8 を、九段が白百合学園小学校の四角を隠した (text_overlaps 4 件)。神保町を北へ 160 m、九段を南へ 160 m、霞が関を東へ 300 m・北へ 120 m ずらした。値と選び方は変えていない | 3 枚とも text_overlaps 0 件。全ての PNG を目で確かめた。拡大図は靖国通りの 8 地点で、横に長い |
| R010 | - | - | done | outputs/ (CSV と summary.txt) | スクリプトのコメントを千代田区に合わせて直した後、prepare.py から summarize.py までを流し直した | CSV と summary.txt の md5 は流し直す前と同じ |
| R011 | B5 | exploratory | done | outputs/route_class.csv | 結果を見た後、出力の外で、`路線コード` 4000〜4999 の 1 件の路線コード (41070、2022 年) と、5000 番台の内訳を本票から数えた。計画では区内に高速自動車国道は無いと見込んでいたが、route_class.csv に 1 件あったため。報告には route_class.csv の 1 件だけを書いた | 位置の誤りか、記録の路線コードの誤りかは確かめていない |

# 記録: 港区の交通事故の傾向 (ロール別レポート)

台東区の型 (2026-11-03、台東区の記録の R020 までの修正を含む) を写して、古い版を全部作り直した。古い版のファイルは同じ名前で上書きした (型に無い古いファイルは無かった)。

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の町丁の検査値を 0 にして 1 回目を流し、止まったときの値を書いた (型の手順どおり) | 東京の本票 205,541 行 (7 年、用意されたファイルを使った)。町丁の境界 140 行、KEY_CODE でまとめて 118 単位、人口 260,486 人。複数行の単位は水面調査区 131030310 (22 行) と台場一丁目 (2 行)。学校 29 校、閉校した学校 2 校 (旧三光小学校、旧神応小学校) を除いた。港区 7,831 行。コードと面の照合: 両方 7,765、コードだけ 65、面だけ 51、位置の無い行 1 |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2025 年の区間 989.4〜1117.5 件は 2019 年の 1242.0〜1385.0 件と重ならない。規則により、2019 年より減ったと書ける。指数は 2020 年 72.6、2025 年 80.2 (23 区は 83.7、101.6) |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 夜 38.1% (2 位)、歩行者 19.7% (6 位)、自転車 30.6% (22 位)、高齢の歩行者 2.8% (23 位)、生活道路 狭い読み 15.1% (20 位)、広い読み 24.4% (21 位)、交差点内 37.4% (20 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 若い歩行者と自転車は 16 時台が最多 (57 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 29 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 20 m で 14/15、50 m で 10/15、高速道路を除いた 30 m で 15/15 が 30 m 以内に残る。高速道路の事故は 309 件、上位 15 の円に 9 件 |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | - | 分位と等間隔で 58.1% の町丁の色が変わる。水面 1 単位 (18 件) は値なし、道路の無い町丁は無い。道路 0.5 km 未満の愛宕二丁目と麻布狸穴町は上位 5 より下 |
| R008 | B4, B5, B6 | exploratory | done | outputs/school-map.json, outputs/hotspots-map.json, outputs/town-rate.json | 結果を見た後、plot.py の地名 (13 か所)、拡大図の範囲 (六本木・西麻布の 5 地点)、番号と地名の位置を決めた。値と選び方は変えていない | 1 回目の text_overlaps は、学校の地図で「六本木」が六本木中学校の四角を、地点の地図で「芝公園」が 3 位の番号に、拡大図で 7 位の番号が 2 位の円に乗っていた。六本木を南へ 170 m、芝公園を東へ 250 m・北へ 120 m、麻布十番を南へ 120 m ずらし、拡大図の 7 を円の左下に移して、3 枚とも 0 件。全ての PNG を目で確かめた |
| R009 | - | - | done | outputs/*.csv, outputs/summary.txt | コメントだけを直して analyze.py、plot.py、summarize.py を流し直した | CSV と summary.txt は R008 と 1 バイトも変わらない (md5 で照合) |

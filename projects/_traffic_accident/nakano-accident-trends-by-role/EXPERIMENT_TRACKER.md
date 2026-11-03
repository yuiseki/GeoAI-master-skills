# 記録: 中野区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の検査値は、1 回目に 0 で流して止め、出た値を書いた (境界ファイル 85 行、KEY_CODE でまとめた後 85 単位、人口 344,880 人) | 東京の本票 205,541 行 (用意されたファイル、md5 3dcf22ae…)、中野区 4,471 行、位置の無い行 0。コードと面の照合: 両方 4,444、コードだけ 27、面だけ 44。年ごとのコードと面の件数は 2019 年の 692 と 692 から 2025 年の 620 と 622 まで、差は年に 0〜7 件で、年をまたぐ跳びは無い。水面調査区、名前の無い単位、複数行の町丁、道路の無い町丁は無い。学校 35 校 (「旧」で始まる名前は無い) |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2021 年の区間 535.7〜631.3 件は 2019 年の 641.4〜745.5 件と重ならない。ほかの年 (2025 年 572.2〜670.8 件を含む) は 2019 年と重なる。規則により、2021 年だけを減ったと書き、2025 年を減ったと書かない |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 自転車 57.2% (2 位)、生活道路 狭い読み 37.9% (2 位)、広い読み 49.4% (3 位)、若い歩行者・自転車 14.3% (4 位)、交差点内 38.0% (19 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全体は 8 時台が最多 (340 件)。若い歩行者と自転車も 8 時台が最多 (71 件、平日 62 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 35 校。円は重なるので足さない。OSM に「中野東中学校」と「中野区立 東中学校」が別の点としてある (確かめていない) |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 20 m で 11/15、50 m で 12/15、首都高速を除いた 30 m で 14/15 が 30 m 以内に残る。首都高速の事故は 80 件、上位 15 の中に 11 件 (9 位に 6 件、6 位に 3 件) |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | 台東区と同じく、階級は classify_map.py で決め、報告に貼る地図は同じ区切りで plot.py が描いた | 分位と等間隔で 77.6% の町丁の色が変わる。85 単位を描き、分析の 85 と合う |
| R008 | - | - | done | outputs/deaths.csv, outputs/summary.txt | - | 16 件のうち亡くなった歩行者 13 人 (65 歳以上が 6 人)。0〜5 時台は 4 件 |
| R009 | B4, B5, B6 | exploratory | done | outputs/hotspots-map.json, outputs/school-map.json, outputs/town-rate.json | 1 回目の図で、地名の弥生町が 13 位の番号と学校の四角 (みなみの小学校) に、中野坂上が中野第一小学校の四角に、江古田が江古田小学校の四角に重なった (text_overlaps 4 件)。弥生町を東へ 450 m、中野坂上を南へ 250 m、江古田を北へ 200 m ずらした (LANDMARK_OFFSETS)。値と選び方は変えていない | 3 枚の地図で text_overlaps 0 件。拡大図 (中野坂上) に入れた地点は 2、3、5、6、9 位 |

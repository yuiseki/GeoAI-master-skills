# 記録: 文京区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R000 | - | - | done | artifacts/_traffic_accident/bunkyo-accident-trends-by-role/towns.parquet | prepare.py の町丁の検査値は台東区の値 (108、211,444) を消し、1 回目に数えた値を書いた。本票と区の面は、置いてあるファイルを使い、行数と年の数を検査する形にした | 1 回目 (2026-11-03): 町丁 68、人口 240,069。この値を `TOWN_COUNT`、`TOWN_POPULATION` にして 2 回目を流し、検査を通った。本票 205,541 行 (md5 3dcf22ae…)、区 23、学校 39、道路 4,643 本 |
| R001 | - | - | done | outputs/analysis.json | analysis.json の commit を `git rev-parse` でなく `.git` のファイルから読むようにした (この作業では git のコマンドを使えないため)。値の計算は変えていない | 東京の本票 205,541 行、文京区 3,124 行。コードと面の照合: 両方 3,098、コードだけ 26、面だけ 27 |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2025 年の区間 418.9〜504.0 件は 2019 年の 372.2〜452.7 件と重なる。規則により増えたと書かない。2021〜2025 年の指数は 110.5〜116.3 |
| R003 | B2 | exploratory | done | outputs/wards.csv | 23 区の順位を、行の位置 (`wards[5]`) でなく区コードで引くようにした (`ward_ranks`)。結果を見る前に直した | 交差点内 38.6% (18 位)、生活道路 狭い読み 18.3% (17 位)、広い読み 29.9% (18 位)、若い歩行者・自転車 12.4% (10 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 若い歩行者と自転車は 17 時台が最多 (36 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 39 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 20 m で 12/15、50 m で 12/15 が 30 m 以内に残る |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | 台東区と同じく、階級は classify_map.py で決め、同じ区切りで plot.py で EPSG:6677 に描いた。入れ替わりの割合は classify_map.py の標準出力を tmp/ に残して読んだ (台東区は図の注記に値を手で書いていた) | 分位と等間隔で 72.1% の町丁の色が変わる (Jenks とは 67.6%) |
| R008 | - | - | done | outputs/deaths.csv | - | 10 件のうち二輪車 5 人、歩行者 3 人 |
| R009 | B1, B5, B6 | exploratory | done | outputs/trend-index.json, outputs/hotspots-map.json, outputs/town-rate.json | 図だけを直した。値と選び方は変えていない。(1) 推移の図の縦軸を、台東区の決め打ち 60〜115 から、帯の範囲に合わせた範囲に変えた (文京区の帯の上端は 127 ほどで、60〜115 では切れるため)。(2) 地名を文京区の町丁から選び直し、拡大図を春日・本郷・湯島にした。(3) 1 回目の地図で 12 位の番号が 5 位の番号と並んで読み分けにくかったので、12 位の番号を左に書いた | 文字の重なりは 3 枚の地図とも 0 件 (1 回目から 0 件。12 位と 5 位は重なりとしては数えられていなかったが、目で見て直した) |

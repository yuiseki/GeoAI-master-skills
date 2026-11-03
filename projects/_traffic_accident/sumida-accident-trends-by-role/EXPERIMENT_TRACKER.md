# 記録: 墨田区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R000 | - | - | done | artifacts/_traffic_accident/sumida-accident-trends-by-role/towns.parquet | prepare.py の町丁の検査値は、1 回目に数えた値を書いた (検査値 0 で流して止め、出た値を入れて流し直した) | 2026-11-03。東京の本票 205,541 行 (ファイルの年 7 つ)、23 区 23 行は用意された版 (md5 3dcf22ae…、cba05bb5…) を使い、行数と年の数を検査した。墨田区の町丁 `TOWN_COUNT` 104、人口 `TOWN_POPULATION` 272,085。学校 36 校、道路 5,100 本 |
| R001 | - | - | done | outputs/analysis.json | 1 回目の結果で 2022 年から件数が増えたのを見た後、渋谷区と同じく、区の面に入る点で数えた年ごとの件数 (`by_year_coded_vs_inside`) を足した。主の読み方は変えていない。git のコマンドを使わない決まりのため、コミットは台東区の `git rev-parse` でなく、渋谷区と同じ `git_head` (.git のファイルを読む) で取った | 東京の本票 205,541 行、墨田区 3,706 行、位置の無い行 0。コードと面の照合: 両方 3,700、コードだけ 6、面だけ 10。増え方は両方の読み方にある (2019 年 454 と 454、2023 年 633 と 632) |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2019 年の区間 413.2〜497.7 件と、2022 年 513.6〜607.3 件、2023 年 584.6〜684.3 件、2025 年 530.9〜626.1 件は重ならない。規則により増えたと書ける。23 区全体の 2025 年の指数は 101.6 |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 交差点内 47.2% (2 位)、夜 31.7% (7 位)、自転車 47.0% (11 位)、生活道路 狭い読み 18.1% (18 位)、広い読み 31.5% (17 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全体は 8 時台が最多 (302 件)。若い歩行者と自転車は 8 時台と 16 時台 (各 40 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 36 校。円は重なるので足さない。OSM の名前に「旧墨田区立 鐘淵中学校」(閉じた学校の名前) が 1 つ入る。台東区と同じ選び方を保ち、除いていない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | 首都高速を除いた 30 m の読みは計画どおり (流す前に決めた) | 20 m で 12/15、50 m で 12/15、首都高速を除いた 30 m で 15/15 が 30 m 以内に残る。区の首都高速の事故は 103 件で、上位 15 の事故には 0 件 |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | 台東区と同じく、階級は classify_map.py で決め、同じ区切りで plot.py が EPSG:6677 に描き直した | 分位と等間隔で 51.9% の町丁の色が変わる (jenks とも 51.9%)。町丁の外の点 6 件。複数行の KEY_CODE と道路の無い町丁は 0 |
| R008 | - | - | done | outputs/deaths.csv | - | 死亡事故 19 件。亡くなったのは二輪車 7 人、歩行者 6 人 (65 歳以上 4 人)、自転車 4 人 |
| R009 | B5, B6 | exploratory | done | outputs/hotspots-map.json, outputs/town-rate.json, outputs/school-map.json | 地名は墨田区の町丁から選び直し、拡大図は 2 位と 5 位 (約 175 m) が並ぶ東向島にした。1 回目の描画で、学校の地図の text_overlaps が 3 件 (両国が両国小学校、錦糸町が錦糸小学校、菊川が中和小学校の四角を隠す) だったので、3 つの地名を LANDMARK_OFFSETS でずらした (両国 南へ 150 m、錦糸町 東へ 230 m、菊川 東へ 130 m)。値と選び方は変えていない | 文字の重なりは 3 枚とも 0 件。拡大図に 2、5、6、7 位。PNG を全て開いて目で確かめた |

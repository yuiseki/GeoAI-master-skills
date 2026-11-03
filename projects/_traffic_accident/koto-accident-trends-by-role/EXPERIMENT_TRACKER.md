# 記録: 江東区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R000 | - | - | done | artifacts/_traffic_accident/koto-accident-trends-by-role/towns.parquet | prepare.py の町丁の検査値は、1 回目に数えた値を書いた (検査値 0 で流して止め、出た値を入れて流し直した)。小地域の表に S_NAME の無い行 (水面 HCODE 8154 の 16 行、名前の無い陸 8101 の 2 行) があったので、prepare.py で HCODE の列を足し、analyze.py で名前を付け、水面には道路あたりの値を付けないと決めた (analyze.py を流す前) | 2026-11-03。東京の本票 205,541 行 (ファイルの年 7 つ)、23 区 23 行は用意された版 (md5 を照合) を使い、行数と年の数を検査した。江東区の町丁 `TOWN_COUNT` 173 行、人口 `TOWN_POPULATION` 524,310。KEY_CODE でまとめて 157 単位。学校 67 校、道路 7,935 本。区の中の道路に首都高速の湾岸線、9 号深川線、7 号小松川線などの motorway があることを確かめた |
| R001 | - | - | done | outputs/analysis.json | 1 回目の結果で 2021 年から 2022 年に件数が跳ねたのを見た後、区の面に入る点で数えた年ごとの件数 (`by_year_coded_vs_inside`) を足した (渋谷区と同じ)。主の読み方は変えていない。1 回目は yearly.csv の区の名前が「台東区」のままだった (analyze.py の文字列の写し漏れ) ので直して流し直した | 東京の本票 205,541 行、江東区 7,853 行、位置の無い行 0。コードと面の照合: 両方 7,798、コードだけ 55、面だけ 34。2022 年はコード 1,273 件、面 1,271 件で、跳ねは両方の読み方にある |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2019 年の区間 944.8〜1,070.1 件と、2022 年 1,204.0〜1,344.9 件、2025 年 1,153.5〜1,291.5 件は重ならない。規則により増えたと書ける。23 区全体の 2025 年の指数は 101.6 |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 自転車 48.8% (8 位)、歩行者 13.6% (21 位)、交差点内 36.8% (21 位)、生活道路 狭い読み 18.1% (19 位)、広い読み 26.8% (19 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全体は 8 時台が最多 (588 件)。若い歩行者と自転車は 16 時台 (94 件)、平日に限ると 8 時台 (74 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 67 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | 首都高速を除いた 30 m の読みは計画どおり (流す前に決めた) | 20 m で 11/15、50 m で 11/15、首都高速を除いた 30 m で 15/15 が 30 m 以内に残る。上位 15 の事故に首都高速は 0 件 (区の首都高速の事故は 188 件) |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | 台東区と同じく、階級は classify_map.py で決め、同じ区切りで plot.py が EPSG:6677 に描き直した。plot.py の町丁の数の照合を、小地域の表の行数 (`TOWN_COUNT` 173) でなく KEY_CODE の単位の数 (analysis.json の `town_units` 157) と比べるように直した (台東区の版のままでは止まる) | 分位と等間隔で 52.6% の町丁の色が変わる (jenks とは 34.0%)。町丁の外の点 55 件、水面の点 85 件 |
| R008 | - | - | done | outputs/deaths.csv, outputs/summary.txt | 結果を見た後、summarize.py に、死亡事故の事故類型と亡くなった人の組、自転車の単独の割合、前半より後半が多い地点の数を足した | 死亡事故 41 件、亡くなった二輪車 16 人 (うち車両単独 5)、歩行者 12 人 (65 歳以上 7 人)、自転車 9 人 |
| R009 | B4, B5, B6 | exploratory | done | outputs/school-map.json, outputs/hotspots-map.json, outputs/town-rate.json | 1 回目の描画で、地名が学校の四角 10 か所と地点の円 2 つと番号 2 つを隠した (学校が区の北に 67 校と密なため)。tmp/place_labels.py で地名ごとに最も小さい移動を探し、9 つの地名を `LANDMARK_OFFSETS` で動かした (最大は大島の西へ 480 m、門前仲町の南へ 330 m)。町丁の地図の欄外の注記の「橋などの事故」は数えていないので消した。値と選び方は変えていない | 文字の重なりは 3 枚とも 0 件。拡大図 (亀戸から南砂) に 3、4、5、6、7、8、9、11、12、14、15 位 |

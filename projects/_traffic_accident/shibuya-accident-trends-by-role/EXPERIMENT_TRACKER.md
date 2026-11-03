# 記録: 渋谷区の交通事故の傾向 (ロール別レポート)

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R000 | - | - | done | artifacts/_traffic_accident/shibuya-accident-trends-by-role/towns.parquet | prepare.py の町丁の検査値は、1 回目に数えた値を書いた (検査値 0 で流して止め、出た値を入れて流し直した) | 2026-11-03。東京の本票 205,541 行 (ファイルの年 7 つ)、23 区 23 行は用意された版を使い、行数と年の数を検査した。渋谷区の町丁 `TOWN_COUNT` 80、人口 `TOWN_POPULATION` 243,883。学校 25 校、道路 6,780 本 |
| R001 | - | - | done | outputs/analysis.json | 1 回目の結果で 2021 年から 2022 年に件数が跳ねたのを見た後、区の面に入る点で数えた年ごとの件数 (`by_year_coded_vs_inside`) を足した。主の読み方は変えていない | 東京の本票 205,541 行、渋谷区 5,109 行、位置の無い行 0。コードと面の照合: 両方 4,999、コードだけ 110、面だけ 79。2022 年はコード 879 件、面 881 件で、跳ねは両方の読み方にある |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2019 年の区間 543.3〜639.6 件と 2022 年 821.8〜939.1 件、2025 年 732.0〜842.9 件は重ならない。規則により増えたと書ける。23 区全体の 2022 年の指数は 101.6 |
| R003 | B2 | exploratory | done | outputs/wards.csv | 台東区の `wards[5]` (並びの 6 番目) の決め打ちを、区コードで引く `ward_ranks` に直した (結果を見る前) | 交差点内 34.5% (23 位)、夜 37.9% (3 位)、生活道路 狭い読み 22.5% (15 位)、広い読み 31.7% (16 位)、特定小型原付 1.2% (2 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 全体は 17 時台が最多 (357 件)。若い歩行者と自転車は 15 時台 (44 件) と 19 時台 (41 件) |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 25 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | 首都高速を除いた 30 m の読みは計画どおり (流す前に決めた) | 20 m で 12/15、50 m で 12/15、首都高速を除いた 30 m で 12/15 が 30 m 以内に残る。上位 15 の事故のうち首都高速は 26 件で、7 位 (山手通り、元代々木町) は 26 件のうち 12 件 |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | 台東区と同じく、階級は classify_map.py で決め、同じ区切りで plot.py が EPSG:6677 に描き直した | 分位と等間隔で 78.7% の町丁の色が変わる (jenks とは 75.0%)。町丁の外の点 110 件 |
| R008 | - | - | done | outputs/deaths.csv | - | 死亡事故 23 件、亡くなった歩行者 14 人 (65 歳以上 7 人) |
| R009 | B5, B6 | exploratory | done | outputs/hotspots-map.json, outputs/town-rate.json, outputs/school-map.json | 1 回目の描画で、円の濃さ (0.35 + 0.015 × 件数) が 44 件で 1 を超えて止まったので、0.95 で頭打ちにした。PNG を見た後、笹塚と幡ケ谷の地名の白地が 3 位と 8 位の円を隠していたので、地名を置く町丁を二丁目から三丁目に移した。値と選び方は変えていない | 文字の重なりは 3 枚とも 0 件。拡大図 (渋谷駅から神宮前) に 1、6、9、10、11、13 位 |

# 記録: 杉並区の交通事故の傾向 (ロール別レポート)

台東区の型 (`../taito-accident-trends-by-role/`、記録の R001〜R019 を直した 2026-11-03 の版) を写し、区に固有の定数だけを直して流した。全ての run は 2026-11-03。

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | prepare.py の町丁の検査値を 0 にして 1 回目を流して止め、出た値 (境界ファイル 139 行、KEY_CODE でまとめた後 139 単位、591,108 人) を `TOWN_COUNT`、`TOWN_UNITS`、`TOWN_POPULATION` に書いて流し直した (計画どおり) | 東京の本票 205,541 行 (渡されたファイル、md5 3dcf22ae…、取り直していない)、杉並区 6,863 行、位置の無い行 0。コードと面の照合: 両方 6,804、コードだけ 59、面だけ 61。年ごとのコードと面の件数の差は 0〜6 件。学校 68 校、閉校した学校 0、水面調査区 0、道路の無い町丁 0、まとめた町丁 0 |
| R002 | B1 | exploratory | done | outputs/yearly.csv | - | 2025 年の区間 940.9〜1066.0 件は 2019 年の 1027.2〜1157.7 件と重なる。規則により減ったと書かない。2020〜2022 年 (801.5〜974.2 件の範囲) は 2019 年の区間と重ならない |
| R003 | B2 | exploratory | done | outputs/wards.csv | - | 生活道路 狭い読み 34.7% (4 位)、広い読み 47.7% (4 位)、交差点内 39.4% (17 位)、夜 26.3% (22 位)、若い歩行者・自転車 12.9% (8 位) |
| R004 | B3 | exploratory | done | outputs/hour_weekday.csv | - | 若い歩行者と自転車は 8 時台が最多 (106 件)、次が 16 時台 (96 件)。平日だけなら 16 時台 83 件、8 時台 82 件 |
| R005 | B4 | exploratory | done | outputs/schools.csv | - | 68 校。円は重なるので足さない |
| R006 | B5 | exploratory | done | outputs/hotspots.csv | - | 20 m で 10/15、50 m で 13/15 が 30 m 以内に残る。首都高速の事故は区で 108 件、上位 15 の円に 4 件 (4 位と 14 位に 2 件ずつ)。除くと 14/15 が残る |
| R007 | B6 | exploratory | done | outputs/towns.csv, outputs/town-rate-quantile.json | - | 分位と等間隔で 77.0% の町丁の色が変わる。道路が 0.5 km より短い町丁は無い。首都高速の件数が最も多い町丁は下高井戸一丁目 (45 件) |
| R008 | - | - | done | outputs/deaths.csv | - | 死亡事故 33 件、死者 34 人。亡くなった側が歩行者の事故 14 件 (65 歳以上 8 件) |
| R009 | B4, B5, B6 | exploratory | done | outputs/school-map.json, outputs/hotspots-map.json, outputs/town-rate.json | 1 回目の学校の地図で、地名「高円寺」が杉並第六小学校の印を、「下高井戸」が高井戸第三小学校と向陽中学校の印を隠した (text_overlaps 3 件)。`LANDMARK_OFFSETS` で高円寺を北へ 250 m、下高井戸を北へ 300 m 動かすと永福と重なったので、西へ 450 m、北へ 200 m にした。値と選び方は変えていない | 3 枚とも text_overlaps 0 件。拡大図 (環七通り、高円寺〜堀ノ内) に 1、3、8、9、10、13、15 位。PNG は全て目で確かめた |
| R010 | B5, B6 | exploratory | done | (出力なし) | 結果を見た後、route_class.csv の「その他」168 件が多いので、`tokyo_honhyo.parquet` から杉並区の「その他」の路線コードを数えた (出力には書いていない)。型の集計は変えていない | 9500 が 67 件、9900 が 60 件、4261 が 30 件、9000 が 9 件、4262 と 7000 が 1 件ずつ。dataset-discovery の npa-traffic-accidents の参照では 4000〜5499 が高速道路 (高速自動車国道と指定の自動車専用道) で、4261 と 4262 は区を通る中央自動車道とみられる (路線の名前は確かめていない)。型の `route_class` は 4000〜4999 を「その他」に入れ、首都高速を除いた読み方でも除かない |
| R011 | B5, B6 | exploratory | done | outputs/route_class.csv, outputs/analysis.json, outputs/towns.csv, outputs/summary.txt | 台東区の型の R020 (高速自動車国道、`路線コード` 4000〜4999 を「その他」から分けた) を写して流し直した (2026-11-03、結果を見た後。R010 の指摘から型が直った)。analyze.py、plot.py、summarize.py の差分だけを写し、区の定数と地名の調整は残した。高速道路を除く読み方と hotspots.csv、towns.csv の `expressway` は 4000〜5499 になり、analysis.json に `other_route_codes` が出る。図の印は [高速道路 n/件] | 高速自動車国道は 31 件、「その他」は 168 件から 137 件 (9500 が 67、9900 が 60、9000 が 9、7000 が 1)。高速道路の事故 (`expressway_points`) は 108 件から 139 件。上位 15 の円の高速道路の事故は 4 件のままで、hotspots.csv、首都高速を除く読み方の地点 (14/15 が残る) と町丁の上位 5 は変わらない。towns.csv で変わったのは `expressway` の 3 町丁 (上高井戸二丁目 0 から 27、久我山二丁目 0 から 3、高井戸西一丁目 0 から 1) だけ。text_overlaps は 3 枚とも 0 件 |

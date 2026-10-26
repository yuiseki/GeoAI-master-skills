# 記録: クマの大量出没の年を、前の年の気温で説明できるか

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R000 | sanity | - | sanity | 県 × 年の秋と年の通報 | akita c7047ab、gifu b7f5947、kyoto a2a50c4、ishikawa d2b77a2 | done | outputs/outcomes.csv | - | 32 行 (秋田 4、岐阜 12、京都 10、石川 6)。岐阜の月の読めない 32 行は年に入れ秋には入れない |
| R001 | sanity | - | sanity | 県の夏の最高気温 | AgERA5 月別 (HF 348e459)、jp-admin e6c87b1 | done | artifacts/bear-outbreak-weather/summer_tmax.csv | geometry の列は DuckDB 2.0 で GEOMETRY('OGC:CRS84') として読まれた (カードは BLOB)。ST_AsWKB を通した | 県の中の 0.1 度格子の中心: 秋田 125、岐阜 106、京都 49、石川 44。欠けた値の月 0 / 1,008 |
| R002 | H1 | H1 | confirmatory | ΔT (前年の夏 − 前々年の夏) と秋の通報 | 同上 | done | outputs/h1.json | - | 順位相関 −0.285、置換の片側 p 0.083 で、規則では判断できない。県ごと: 秋田 −0.60、京都 −0.67、石川 −0.43、岐阜 +0.62。年の全期間 −0.299 (p 0.073)、傾向を除いて −0.250 (p 0.099)。反証の未来の ΔT も −0.384 (両側 p 0.055) で、区別できない。県を 1 つずつ外すと −0.06〜−0.73 |
| R003 | sanity | - | sanity | 夏の日射量 (日別) と降水量 (月別) | AgERA5 SRF、PF-M (FAO の COG、2026-10-26 取得) | done | artifacts/bear-outbreak-weather/solar_precip.csv | - | 日射は 1,763 日 (目録に 77 日分が無い)。夏ごとの日数 74〜92。画素数は気温と同じ |
| R004 | 探索 | - | exploratory | 気象の 9 つの値と秋の通報 | 同上 | done | outputs/explore_weather.json | 結果を見た後に追加 | Bonferroni の目安 0.0056 に届いたものは無い。当年の夏の気温 +0.257 (p 0.063)、気温の前年比 +0.286 (p 0.164)、日射の前年比 +0.239 (p 0.259)。県ごとに向きがそろわない (岐阜がたびたび逆) |

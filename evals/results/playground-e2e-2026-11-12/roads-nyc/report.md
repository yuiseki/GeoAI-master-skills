# ニューヨーク市の幹線道路: 2026 年 9 月の平日の朝と夕のラッシュの遅れと、読めなさ

## 問題設定

NYC DOT の旅行時間のオープンデータ (5 分ごとの区間の旅行時間と速度) で、朝 (AM) と夕 (PM) のラッシュにどの路線の遅れが大きく、どの区間の所要時間が読めないか、朝と夕の差はどれだけ確かか、を示す。使い道は、遅れと読めなさの大きい場所の優先順位づけ。道路の管理者や利用者が、朝と夕のどちらを、どの区間で警戒するかを見る。予測の問いではない。過去の観測の要約と、その不確かさの問い。

- 遅れ: 自由流の旅行時間との比 (TTI) と、1 回の通行あたりの遅延 (秒、分)。
- 読めなさ: LOTTR (旅行時間の 80 パーセンタイル / 50 パーセンタイル。FHWA の国の指標で、1.5 以上を信頼できないとする) と、PTI (95 パーセンタイル / 自由流)。
- 時間帯: FHWA の決まりに合わせ、AM は平日の 06:00〜10:00、PM は平日の 16:00〜20:00 (地方時)。祝日の 2026-09-07 (Labor Day) は週末として外す。2026 年 9 月の平日は 21 日。
- 手順は `.agents/skills/travel-time-reliability/SKILL.md` に従った。計画 (`EXPERIMENT_PLAN.md`) は作っていない。比較の設定 (時間帯、自由流、行の除き方) を結果を見てから選べるが、主の設定は FHWA の決まりと skill の既定に固定し、変えた結果は頑健性の節に並べたため。

問い: 2026 年 9 月の平日の AM (06〜10 時) と PM (16〜20 時) の NYC の道路で、どの路線の遅れが大きく、どの区間の所要時間が読めないか、PM − AM の差とその 95% 区間はいくつか。

結論: 要点を表にする。詳細は末尾の「結論と限界」にある。

| 番号 | 要点 | 数字 | 根拠 |
|---|---|---|---|
| 1 | PM の遅延が最大の路線は VWE 南行 (Northern Blvd → Belt Pkwy、8.69 mi)。AM で最大は GOW 北行 (92nd St → Atlantic Av) | PM の遅延 33.35 分、PM TTI 2.10 ([table_routes.csv](outputs/table_routes.csv))。GOW 北行は AM の遅延 25.51 分 | [表 1](#表-1-路線の遅れと朝夕の差) |
| 2 | 区間では BQE 南行 (Leonard St → Atlantic Av) の PM が最大。ただし自由流の速度が低い区間は TTI が過小になりうる | PM の遅延 1,474.9 秒、PM TTI 5.29 ([table_top_delay_PM.csv](outputs/table_top_delay_PM.csv)) | [表 2](#表-2-区間の-pm-の遅れ上位) |
| 3 | 読めない区間 (LOTTR ≥ 1.5、AM か PM のどちらか) は、10 日以上の観測がある区間のうち 34 / 80。95% 区間の下限まで 1.5 以上なのは 9 | AM 24、PM 16、両方 6 ([summary_numbers.json](outputs/summary_numbers.json)、[table_unreliable_links.csv](outputs/table_unreliable_links.csv)) | [表 3](#表-3-読めない区間-lottr--15) |
| 4 | 朝と夕の差は、PM が遅い区間が多い。区間 80 のうち、PM が遅い (95% 区間が 0 を含まず正) のは 47、AM が遅いのは 16、0 を含むのは 17。路線 17 では順に 12、4、1 | 区間の 95% 区間の幅の中央値 83.7 秒 ([summary_numbers.json](outputs/summary_numbers.json)) | [図 1](#図-1-路線の-pm-から-am-を引いた差), [表 4](#表-4-朝と夕の差が大きい区間) |
| 5 | 平均の速さの順位は、読めなさの順位の代わりにならない | PM の平均速度の順位と LOTTR の Spearman 0.45。LOTTR ≥ 1.5 の 34 区間のうち、PM の平均速度が低い 20 区間に入らないのは 24 ([summary_numbers.json](outputs/summary_numbers.json)) | [基準](#基準) |
| 6 | 遅れの順位は日を分けても再現し、読めなさの順位は再現が弱い | 前半と後半の Spearman: PM の遅延 0.974、PM の LOTTR 0.768 ([split_half_stability.csv](outputs/split_half_stability.csv)) | [表 6](#表-6-前半と後半の順位の再現) |

## データの確認

データ: NYC Open Data「DOT Traffic Speeds」(Socrata リソース i4gi-tjb9、https://data.cityofnewyork.us/resource/i4gi-tjb9.json) の 2026-09-01〜2026-09-30 の 1,056,287 行 (2026-11-12 に取得。サーバ側の件数 1,056,287 と一致、[server_count.txt](outputs/server_count.txt))。区間 125 本。ライセンス欄は空で、NYC Open Data の利用規約に従う。

| 確かめた項目 | 結果 | 出力 |
|---|---|---|
| 状態の符号 | 状態 0: 603,090 行 (速度の中央値 42.87 mph)。状態 −101: 453,197 行 (速度の中央値 0、うち旅行時間 ≤ 0 が 403,413 行)。−101 は「観測なし」と読み、主の分析では外した | [check_status.csv](outputs/check_status.csv) |
| 状態 0 を持つ区間 | 94 本。残り 31 本は 1 行も無く、指標を出せない | [data_checks.json](outputs/data_checks.json) |
| 状態 0 の割合の偏り | 平日の時刻別で 0.464〜0.604。混雑の時間に観測なしが偏るようには見えない | [check_status0_share_by_hour.csv](outputs/check_status0_share_by_hour.csv) |
| 報告の間隔 | 中央値 300 秒 | [data_checks.json](outputs/data_checks.json) |
| 同じ値の繰り返し | 状態 0 の連続行で、区間ごとの割合の中央値 0.062、最大 0.440 | [data_checks.json](outputs/data_checks.json) |
| 時計 | 平日の速度の中央値は 4 時台が最速 (51.57 mph)、17 時台が最遅 (25.47 mph)。地方時と読める | [check_hourly_speed_status0.csv](outputs/check_hourly_speed_status0.csv) |
| 日の欠け | 9 月 1 日 26,144 行、2 日 23,106 行、16 日 35,125 行。ほかの日は約 36,000 行 (125 本 × 288) | [check_rows_by_day.csv](outputs/check_rows_by_day.csv) |
| 15 分の区切りへの集約 | 603,090 行 → 207,146 区切り。除いた行 0 | [bins_audit_main.json](outputs/bins_audit_main.json) |
| 分析に使えた区間 | 指標を出せた区間 94 本のうち、AM と PM の両方に 10 日以上あるのは 80 本。10 日未満は 14 本で順位から外す (表には出す) | [table_links_all.csv](outputs/table_links_all.csv) |
| 区間の長さ | 速度 × 旅行時間の中央値から求めた。地図上の長さとは照合していない | [link_length_mi.csv](outputs/link_length_mi.csv) |

使い道に合わせた注意は 3 つ。(1) 区間の名前は、交差点や出口の間で、高速道路、橋、トンネルが混じる。「幹線道路」はこの 125 本の範囲で、市内の全ての幹線ではない。(2) 速度は DOT が報告した値で、独立の速度の源 (GPS など) とは突き合わせていない。(3) 区間の形 (`link_points`) は、最後の点が切れていて、地図の表示にだけ使った。

### 基準

記述の問いなので、予測の基準の代わりに、2 つの単純な基準と比べた。

1. 平均の速さだけで順位を付ける基準。PM の平均速度 (長さ ÷ 平均の旅行時間) の低い順を「遅れ」の順位とし、LOTTR の順位と比べる。Spearman 0.45。PM の平均速度の低い 20 区間と LOTTR の上位 20 区間の重なりは 6。LOTTR ≥ 1.5 の 34 区間のうち、遅い 20 区間に入らないのは 24。遅さと読めなさは別の軸で、遅さの順位では読めない区間を拾えない ([summary_numbers.json](outputs/summary_numbers.json))。
2. 朝と夕の差がゼロの基準。区間ごとの日ごとの PM − AM のうち、PM が遅い日の割合の中央値は 0.799。差ゼロなら 0.5 になるはずで、朝夕は同じという基準は多くの区間で合わない。

## 評価の設計

出す量は記述の要約で、予測ではない。評価は、次の 3 つで「その順位や差が、観測した日の取り方にどれだけ左右されるか」を測る。

- 不確かさ: 日を復元抽出で引き直す (1,000 回)。日ごとの PM − AM の平均を作り、両方の時間帯に観測のある日だけ使う。LOTTR、TTI、PTI の区間も、区間 × 時間帯ごとに日を引き直す。朝と夕の差には、符号反転の検定 (20,000 回) の p 値を作り、Benjamini–Hochberg で補正した (q)。日は互いに独立ではない (週のまとまり) ので、暦の週を 5 つのブロックとして引き直した区間も出す。
- 再現: 日を前半 (9/1〜9/16) と後半、奇数日と偶数日に分け、順位が分け方の間で保たれるかを見る。時間の順の予測ではなく、順位の再現性の見積もり。
- 設定の変更: 状態 −101 の行、繰り返し値、特定の日、自由流の決め方、時間帯の窓、1 日 1 時間帯あたりの区切りの最小数を変える。

## モデルまたは手法

方法: 機械学習のモデルは使わない。問い (何が遅く、何が読めないか) は、観測した旅行時間の要約で答えられ、回帰、GWR、空間の統計を足してもこの問いには答えが増えないため。要約は skill `travel-time-reliability` の `ttr_metrics.py` の関数 (15 分の区切り、LOTTR、TTI、PTI、遅延、日の引き直し) を使い、足りない部分 (区間と時間帯の区間推定、路線、符号反転検定、週のブロック、設定の変更) は `scripts/05_analysis.py`、`06_robustness.py` で書いた。skill の単体試験 (7 件) は通っている。

- 区切り: 区間 × 15 分の平均の旅行時間 (FHWA の単位)。
- 自由流: 区間ごとの 00〜05 時の 15 分の区切りの 15 パーセンタイル (skill の既定。FHWA の決まりではない)。自由流の速度 (長さ ÷ 自由流の時間) が 30 mph 未満の区間は「自由流が疑わしい」と印を付けた。
- 路線: 連続する区間の鎖 (人が名前から選んだ 17 の鎖、`05_analysis.py` の `ROUTES`)。15 分の区切りごとに、全区間がそろった区切りだけ旅行時間を足す。路線の値は観測ではなく派生で、来歴は [PROVENANCE.json](../../artifacts/nyc-arterial-reliability/PROVENANCE.json) にある。名前から鎖を決めたので、実際の道のつながりとは照合していない。
- 同じ時刻の日ごとの LOTTR: ピーク内の時刻の変化を除くため、同じ時刻の区切り (10 日以上) で日をまたいで p80 / p50 を作り、時間帯の中央値を取る。
- 空間の手法が要るかの判定: 近い単位が似ることはあるが (同じ路線の区間は同じ渋滞を共有する)、問いは空間の構造そのもの (集まり、届き方) ではなく、特定の区間と路線の値。空間の構造を無視しても、結論の数字は変わらないが、同じ路線の区間は独立でない。そのため、路線に足した値を別に出した。Moran's I、GWR、空間の交差検証は、問いに要らないので足さない。MAUP の格子の掃引も、単位が感知器の区間で、観測の過程が決めるので省いた。
- 実行の上限: この環境に systemd-run が無かったため、`ulimit -v` でメモリに上限を掛けた (CPU の上限は未設定)。

失敗の型:

| ID | 判定 | 根拠 |
|---|---|---|
| F1 | 確かめた | (もっともらしい数字を出すバグ) 行数を段ごとに数えた (1,056,287 行がサーバ側の件数と一致、[server_count.txt](outputs/server_count.txt))。集約の行数は [bins_audit_main.json](outputs/bins_audit_main.json)。skill の単体試験 7 件が通った |
| F2 | 確かめた | (弱い基準) 平均速度の順位と、朝夕の差ゼロを基準にした (基準の節) |
| F3 | 当てはまらない | (漏れ) 予測ではなく同じ月の要約。自由流は同じ月の夜から作るが、LOTTR は自由流を使わず (自由流を変えても LOTTR の順位の Spearman は 1.000、[robustness_summary.csv](outputs/robustness_summary.csv))、TTI の順位は変える設定で確かめた |
| F4 | 確かめた | (近道) 状態 −101、繰り返し値、時間帯の窓を変えた ([robustness_summary.csv](outputs/robustness_summary.csv)) |
| F5 | 確かめた | (想定外の結果を発見として語る) 自由流が 30 mph 未満の区間 12 本が、遅さの上位に入る。これは発見ではなく、測定か自由流の定義の問題の可能性として書き、理由は分けていない |
| F6 | 確かめた | (書いた方法と流した方法の食い違い) 報告の表は `scripts/08_build_report.py` が CSV から組む。時間帯と自由流は skill の定義を使った |
| F7 | 確かめた | (早い段階の枠の固定) 主の設定 (FHWA の窓、skill の自由流) は結果を見る前に決め、変えた設定は並べた |
| F8 | 確かめた | (出どころの無い数字) 数字は outputs/ の CSV と JSON から写し、`check_project.py` で照合した |
| F9 | 確かめた | (データの取り違え) 期間、件数をサーバの値と照合した。ただし配布元のその後の訂正の有無は未確認 |

## 結果と誤差の分析

### 表 1: 路線の遅れと朝夕の差

PM の遅延の大きい順。遅延は 1 回の通行あたりの分。PM − AM は日の引き直しの 95% 区間 (日数は 12〜21、[table_routes.csv](outputs/table_routes.csv))。

| 路線 (方向と区間) | 長さ mi | PM の遅延 分 | AM の遅延 分 | PM TTI | AM TTI | PM の LOTTR | AM の LOTTR | PM − AM 秒 [95% 区間] | BH 補正 q |
|---|---|---|---|---|---|---|---|---|---|
| VWE S (Northern Blvd-Belt Pkwy) | 8.69 | 33.35 | 13.42 | 2.10 | 1.44 | 1.17 | 1.33 | 1,131.6 [819.5, 1,447.3] | 0.000 |
| Belt/Laurelton W (SSP-VWE) | 6.88 | 24.26 | 18.42 | 2.62 | 2.23 | 1.13 | 1.21 | 313.3 [75.5, 524.0] | 0.043 |
| GOW N (92nd St-Atlantic Av) | 5.79 | 18.98 | 25.51 | 3.74 | 4.68 | 1.37 | 1.41 | -406.6 [-600.7, -208.6] | 0.004 |
| FDR N (Catherine Slip-63rd St) | 4.71 | 18.75 | 11.04 | 3.89 | 2.70 | 1.73 | 1.78 | 515.8 [147.5, 877.9] | 0.020 |
| CIP N (Laurelton Pkwy-LIE) | 5.18 | 13.24 | 16.17 | 3.19 | 3.68 | 1.36 | 1.39 | -171.4 [-430.2, 71.1] | 0.284 |
| FDR S (63rd St-Brooklyn Br) | 5.45 | 12.82 | 2.80 | 2.77 | 1.39 | 1.24 | 1.22 | 528.5 [424.8, 623.0] | 0.000 |
| CIP S (LIE-Laurelton Pkwy) | 5.14 | 8.54 | 2.14 | 2.52 | 1.38 | 1.24 | 1.28 | 390.7 [315.6, 487.1] | 0.000 |
| SIE W (Bradley Av-South Av) | 2.26 | 4.48 | 0.61 | 3.25 | 1.31 | 1.18 | 1.13 | 228.7 [187.9, 268.3] | 0.000 |
| HRP S-BWB S (Lafayette Av-Queens) | 1.99 | 3.09 | 1.93 | 2.34 | 1.84 | 1.42 | 1.68 | 78.6 [29.8, 131.3] | 0.011 |
| BE S (Griswold Av-Stratford Av) | 3.30 | 2.91 | 6.65 | 1.83 | 2.90 | 1.36 | 1.50 | -218.3 [-330.4, -114.3] | 0.002 |
| VWE N (Jewel Av-Linden Pl) | 2.96 | 2.71 | 1.01 | 1.81 | 1.30 | 1.64 | 1.12 | 97.4 [11.6, 190.6] | 0.063 |
| GOW S (Atlantic Av-92nd St) | 5.81 | 2.62 | 1.44 | 1.38 | 1.21 | 1.11 | 1.05 | 70.6 [34.5, 105.5] | 0.002 |
| CBE E (Taylor Av-Waterbury Av) | 3.00 | 1.70 | 0.76 | 1.50 | 1.22 | 1.20 | 1.17 | 55.4 [21.2, 96.4] | 0.002 |
| SIE E (South Av-Wooley Av) | 1.82 | 1.33 | 3.17 | 1.73 | 2.75 | 1.23 | 1.57 | -108.7 [-151.0, -67.5] | 0.001 |
| BE N (Stratford Av-Griswold Av) | 3.36 | 1.29 | 0.62 | 1.36 | 1.18 | 1.17 | 1.19 | 39.0 [2.8, 84.2] | 0.084 |
| WSE S (South Av-Bloomingdale Rd) | 4.40 | 0.90 | 0.36 | 1.21 | 1.08 | 1.11 | 1.03 | 32.3 [22.8, 42.2] | 0.000 |
| WSE N (Bloomingdale Rd-South Av) | 4.45 | 0.80 | 2.91 | 1.19 | 1.68 | 1.03 | 1.29 | -125.4 [-179.1, -73.1] | 0.001 |

自由流の速度が 30 mph 未満の路線は 2 (上位 2 路線の VWE 南行と Belt/Laurelton 西行)。夜も遅いので、自由流の旅行時間が長めに出て、遅延と TTI は小さめに出る。上位 2 路線の順位は、より遅い (下限寄り) 側へ頑健だが、大きさは確かでない。

### 図 1: 路線の PM から AM を引いた差

![図 1](figures/fig1_route_pm_minus_am.png)

青は日の引き直し、灰色は暦の週 5 ブロックの引き直しの 95% 区間。0 を挟む路線は 1 つだけ (CIP 北行)。12 路線は PM が遅く、4 路線 (GOW 北行、BE 南行、SIE 東行、WSE 北行) は AM が遅い ([summary_numbers.json](outputs/summary_numbers.json))。区間の中央値の幅は、日の引き直しで 83.7 秒、週の引き直しで 83.8 秒で、ほぼ同じ。ただし週のブロックは 5 つしかなく、区間は粗い。

### 表 2: 区間の PM の遅れ上位

[table_top_delay_PM.csv](outputs/table_top_delay_PM.csv) の上位 10 (10 日以上の区間)。

| 区間 | 長さ mi | PM の平均 秒 | PM の遅延 秒 | PM TTI | PM の LOTTR | 自由流の速度 mph |
|---|---|---|---|---|---|---|
| BQE S LEONARD STREET - ATLANTIC AVENUE | 4.23 | 1,818.5 | 1,474.9 | 5.29 | 1.10 | 44.4 |
| Belt Pkwy W JFK Expressway - VWE N Jamaica Ave | 3.29 | 1,948.1 | 1,315.5 | 3.08 | 1.14 | 18.7 |
| BQE N ATLANTIC AVENUE - LEONARD STREET | 4.15 | 1,165.4 | 837.4 | 3.55 | 1.44 | 45.5 |
| Belt Pkwy E 182nd St - Laurelton Pkwy N @ SSP | 2.52 | 1,020.0 | 823.0 | 5.18 | 1.30 | 46.0 |
| VWE S MP2.66 (Exit 2 Rockaway Blvd) - Belt Pkwy E 182nd St | 2.93 | 1,445.8 | 761.7 | 2.11 | 1.18 | 15.4 |
| GOW N 9TH STREET - ATLANTIC AVENUE | 1.11 | 836.0 | 748.0 | 9.50 | 1.18 | 45.4 |
| VWE S MP6.39 (Exit 11 Jewel Ave) - MP4.63 (Exit 6 Jamaica Ave) | 2.42 | 1,235.2 | 715.5 | 2.38 | 1.18 | 16.8 |
| Laurelton Pkwy N @ SSP - CIP N Hempstead Tpk | 2.14 | 868.6 | 700.9 | 5.18 | 1.46 | 46.0 |
| FDR N 25th - 63rd St | 1.89 | 768.0 | 620.0 | 5.19 | 1.49 | 45.9 |
| MDE S HARLEM RIVER PARK - GWB W AMSTERDAM AVENUE UPPER LEVEL | 1.18 | 821.2 | 551.9 | 3.05 | 1.23 | 15.8 |

上位 10 のうち、自由流の速度が 30 mph 未満の区間は 4 (Belt Pkwy 西行 JFK → VWE、VWE 南行の 2 区間、MDE 南行の上層)。GOW 北行 9th St → Atlantic Av は PM TTI が 9.50 だが、平日の昼間の速度の中央値が 5 mph 前後で動かない区間で ([check_gow_9th_atlantic_hourly_speed.csv](outputs/check_gow_9th_atlantic_hourly_speed.csv))、測定の異常かどうかは分けていない。AM の上位は次の通り ([table_top_delay_AM.csv](outputs/table_top_delay_AM.csv))。

| 区間 | AM の日数 | AM の平均 秒 | AM の遅延 秒 | AM TTI | AM の LOTTR | 自由流の速度 mph |
|---|---|---|---|---|---|---|
| LIE W 108TH ST - 84TH ST | 13 | 1,301.4 | 1,123.3 | 7.31 | 4.63 | 27.6 |
| Belt Pkwy W JFK Expressway - VWE N Jamaica Ave | 21 | 1,534.1 | 901.5 | 2.42 | 1.27 | 18.7 |
| Laurelton Pkwy N @ SSP - CIP N Hempstead Tpk | 21 | 858.4 | 690.8 | 5.12 | 1.63 | 46.0 |
| GOW N 7TH AVENUE - 9TH STREET | 21 | 916.0 | 676.3 | 3.82 | 1.74 | 52.5 |
| GOW N 9TH STREET - ATLANTIC AVENUE | 21 | 712.7 | 624.7 | 8.10 | 1.07 | 45.4 |
| Belt Pkwy E 182nd St - Laurelton Pkwy N @ SSP | 21 | 798.1 | 601.1 | 4.05 | 1.54 | 46.0 |

LIE 西行 (108th St → 84th St) は、AM と PM の観測が 10 日台前半で、区切りの数が少ない。順位の根拠として弱い。

### 表 3: 読めない区間 (LOTTR ≥ 1.5)

LOTTR の大きい順 ([table_unreliable_links.csv](outputs/table_unreliable_links.csv))。上位 12。

| 区間 | 日数 AM/PM | AM の LOTTR [95% 区間] | PM の LOTTR [95% 区間] | PM の PTI | 同じ時刻の日ごと LOTTR AM/PM |
|---|---|---|---|---|---|
| LIE W 108TH ST - 84TH ST | 13/12 | 4.63 [1.20, 5.14] | 4.97 [1.27, 5.65] | 10.8 | 3.46/3.24 |
| FDR N Catherine Slip - 25th St | 21/21 | 2.13 [1.57, 2.51] | 2.36 [1.80, 3.43] | 9.6 | 1.40/2.31 |
| VWE S MP8.65 (Exit 13 Northern Blvd) - MP6.39 (Exit 11 Jewel Ave) | 21/21 | 1.03 [1.02, 1.05] | 2.31 [1.90, 2.57] | 4.9 | 1.02/1.24 |
| BE S Griswold - Castle Hill Avenue | 21/21 | 2.12 [1.71, 2.58] | 1.27 [1.10, 1.91] | 2.9 | 1.34/1.23 |
| BKN Bridge Manhattan Side - FDR N Catherine Slip | 20/21 | 2.10 [1.66, 2.48] | 1.49 [1.36, 1.69] | 6.5 | 1.31/1.44 |
| HRP S Lafayette Ave - BWB S Toll Plaza | 19/20 | 1.93 [1.54, 2.15] | 1.79 [1.50, 2.32] | 7.8 | 1.61/1.77 |
| FDR N 25th - 63rd St | 21/21 | 1.89 [1.61, 2.05] | 1.49 [1.31, 1.66] | 9.7 | 1.34/1.37 |
| GOW N 7TH AVENUE - 9TH STREET | 21/21 | 1.74 [1.50, 1.94] | 1.88 [1.48, 2.23] | 5.3 | 1.18/1.40 |
| SIE E CLOVE ROAD - FINGERBOARD ROAD | 20/21 | 1.85 [1.65, 2.30] | 1.03 [1.02, 1.04] | 1.2 | 1.43/1.02 |
| SIE W - WSE S SOUTH AVENUE - SOUTH AVENUE | 19/20 | 1.03 [1.02, 1.04] | 1.85 [1.42, 1.93] | 2.8 | 1.02/1.38 |
| BWB S Toll Plaza - Queens Anchorage | 21/21 | 1.83 [1.48, 2.13] | 1.16 [1.09, 1.25] | 3.0 | 1.34/1.13 |
| FDR S Catherine Slip - BKN Bridge Manhattan Side | 21/21 | 1.22 [1.15, 1.39] | 1.83 [1.34, 2.21] | 5.9 | 1.10/1.50 |

LOTTR は 16 区切りのピーク全体をまとめたもので、ピーク内の時刻による遅れの変化も含む。同じ時刻に日をまたいで比べた LOTTR の PM の中央値は 1.19、ピーク全体の LOTTR の PM の中央値は 1.24 (区間の中央値)。同じ時刻の日ごとの LOTTR が 1.5 以上の区間は AM 4、PM 6。つまり、日による揺れが大きい区間は、LOTTR ≥ 1.5 の 34 区間よりずっと少ない。PTI の大きい区間 (PM) は [table_top_pti_PM.csv](outputs/table_top_pti_PM.csv) にある。

### 表 4: 朝と夕の差が大きい区間

PM が遅い区間 (上位 6、[table_diff_pm_slower.csv](outputs/table_diff_pm_slower.csv))。

| 区間 | 日数 | AM の平均 秒 | PM の平均 秒 | PM − AM 秒 [95% 区間] | BH 補正 q |
|---|---|---|---|---|---|
| BQE S LEONARD STREET - ATLANTIC AVENUE | 21 | 763.4 | 1,818.5 | 1,051.3 [939.7, 1,157.5] | 0.000 |
| BQE N ATLANTIC AVENUE - LEONARD STREET | 21 | 551.2 | 1,165.4 | 605.2 [420.4, 772.8] | 0.000 |
| MDE S HARLEM RIVER PARK - GWB W AMSTERDAM AVENUE UPPER LEVEL | 21 | 380.1 | 821.2 | 436.0 [372.8, 506.2] | 0.000 |
| VWE S MP6.39 (Exit 11 Jewel Ave) - MP4.63 (Exit 6 Jamaica Ave) | 21 | 799.0 | 1,235.2 | 422.1 [319.7, 513.3] | 0.000 |
| Belt Pkwy W JFK Expressway - VWE N Jamaica Ave | 21 | 1,534.1 | 1,948.1 | 409.9 [273.9, 541.3] | 0.000 |
| FDR N 25th - 63rd St | 21 | 358.4 | 768.0 | 404.9 [294.2, 512.0] | 0.000 |

AM が遅い区間 (上位 5、[table_diff_am_slower.csv](outputs/table_diff_am_slower.csv))。

| 区間 | 日数 | AM の平均 秒 | PM の平均 秒 | PM − AM 秒 [95% 区間] | BH 補正 q |
|---|---|---|---|---|---|
| LIE W 108TH ST - 84TH ST | 12 | 1,301.4 | 659.7 | -705.5 [-1,229.1, -224.4] | 0.026 |
| GOW N 7TH AVENUE - 9TH STREET | 21 | 916.0 | 622.7 | -308.5 [-435.1, -177.6] | 0.001 |
| GOW N 92ND STREET - 7TH AVENUE | 21 | 317.9 | 96.0 | -217.0 [-264.0, -166.8] | 0.000 |
| CIP N Hempstead Tpk - LIE | 21 | 477.2 | 282.0 | -195.0 [-249.0, -145.3] | 0.000 |
| BE S CASTLE HILL AVENUE - STRATFORD AVENUE | 21 | 320.2 | 187.1 | -129.6 [-183.5, -78.3] | 0.000 |

符号反転検定の BH 補正で有意 (q < 0.05) な区間は 59 ([summary_numbers.json](outputs/summary_numbers.json))。日の引き直しの区間が 0 を含まない数 (PM が遅い 47 と AM が遅い 16 の合計) とは少し違う。週の引き直しで 0 を含まない数は PM が遅い 45、AM が遅い 18。

### 図 2: 遅れと読めなさ

![図 2](figures/fig2_delay_vs_lottr.png)

横軸が遅延、縦軸が LOTTR (95% 区間つき)、破線が 1.5。遅い区間が読めないとは限らない。PM の遅延と LOTTR の Spearman は 0.49 ([summary_numbers.json](outputs/summary_numbers.json))。

### 図 3: 地図

![図 3](figures/fig3_map.png)

左が PM の遅延、右が AM と PM の LOTTR の大きい方。経緯度のまま描いた表示用で、距離や面積は測っていない。灰色は指標を出せなかった区間。

## 疑ったことと、その確認

### 設定を変えたときの頑健性

S0 が主の設定。ほかは 1 つずつ変えた ([robustness_summary.csv](outputs/robustness_summary.csv))。

| 設定 | PM の遅延 上位 10 の一致 | PM の遅延 順位の Spearman | LOTTR ≥ 1.5 の区間数 | S0 と同じ集合の数 | 朝夕の差の符号の一致率 | BH 有意な区間と路線の数 |
|---|---|---|---|---|---|---|
| S0_main | 10 | 1.000 | 34 (母数 81) | 34 | 1.000 | 73 (母数 97) |
| S1_include_status_-101_positive_tt | 9 | 0.991 | 39 (母数 83) | 34 | 0.969 | 71 (母数 100) |
| S2_drop_repeated_values | 10 | 1.000 | 33 (母数 81) | 33 | 1.000 | 73 (母数 97) |
| S3_drop_2026-09-21_(Yom_Kippur) | 10 | 1.000 | 32 (母数 81) | 31 | 0.979 | 72 (母数 97) |
| S4_drop_2026-09-01..04 | 9 | 0.999 | 27 (母数 79) | 25 | 0.989 | 77 (母数 94) |
| S5_free_flow_all_hours_p15 | 9 | 0.998 | 34 (母数 81) | 34 | 1.000 | 73 (母数 97) |
| S6_windows_AM7-10_PM16-19 | 9 | 0.997 | 27 (母数 81) | 23 | 0.969 | 67 (母数 97) |
| S7_min_8_bins_per_day_period | 10 | 0.999 | 32 (母数 80) | 32 | 0.990 | 70 (母数 97) |

読み方: 遅れの順位 (PM の遅延、TTI) は、PM の遅延の Spearman はどの設定でも 0.991 以上 (TTI は 0.986 以上) で、上位 10 の一致は 9〜10 (状態 −101 の行を足した S1 では 9)。読めない区間の数は、時間帯の窓を狭めた S6 と、9 月 1〜4 日を外した S4 で 34 から 27 に減る。つまり、LOTTR ≥ 1.5 の区間の集合は、時間帯の窓と日の取り方に左右され、「34 区間」は点推定として扱えない。朝夕の差の符号は 96.9% 以上で一致する。

### 前半と後半の再現

### 表 6: 前半と後半の順位の再現

([split_half_stability.csv](outputs/split_half_stability.csv)。区間と路線を合わせた順位。日数 5 以上)

| 分け方 | 時間帯 | 指標 | n | Spearman | 上位 10 の一致 (差は符号の一致率) |
|---|---|---|---|---|---|
| first_vs_second_half | PM | delay_s | 94 | 0.974 | 6.000 |
| first_vs_second_half | PM | tti | 94 | 0.952 | 9.000 |
| first_vs_second_half | PM | pti | 94 | 0.901 | 8.000 |
| first_vs_second_half | AM | delay_s | 93 | 0.959 | 8.000 |
| first_vs_second_half | AM | tti | 93 | 0.949 | 8.000 |
| first_vs_second_half | PM | lottr | 94 | 0.768 | 5.000 |
| first_vs_second_half | AM | lottr | 94 | 0.898 | 5.000 |
| first_vs_second_half | PM-AM | diff_s | 93 | 0.842 | 0.946 |
| odd_vs_even_day | PM | delay_s | 96 | 0.981 | 7.000 |
| odd_vs_even_day | PM | tti | 96 | 0.965 | 9.000 |
| odd_vs_even_day | PM | pti | 96 | 0.912 | 9.000 |
| odd_vs_even_day | AM | delay_s | 96 | 0.974 | 9.000 |
| odd_vs_even_day | AM | tti | 96 | 0.958 | 8.000 |
| odd_vs_even_day | PM | lottr | 97 | 0.878 | 8.000 |
| odd_vs_even_day | AM | lottr | 98 | 0.925 | 6.000 |
| odd_vs_even_day | PM-AM | diff_s | 97 | 0.893 | 0.928 |

PM の遅延の順位は Spearman 0.97 台で再現する。LOTTR の順位は 0.77〜0.93 と弱く、上位 10 の一致は 5〜8 に落ちる。読めなさの上位は、日の取り方で入れ替わる。朝夕の差の符号は、前半と後半で 0.946、奇数日と偶数日で 0.928 の区間で一致する (表の最後の行の列)。

### リーク、自由流、測定の問題

- リーク: 予測でないので、答えの言い換えや試験側の情報を入れる問題は当てはまらない。自由流は同じ月の夜から作る。LOTTR は自由流を使わない。
- 自由流が疑わしい区間 ([table_ff_doubtful.csv](outputs/table_ff_doubtful.csv)): 自由流の速度が 30 mph 未満の区間が 12 本。夜 (00〜05 時) でも遅いので、遅延と TTI は、実際より小さく出ている。自由流を 1 日全体の 15 パーセンタイルに変えた S5 でも、順位は Spearman 0.991 (TTI) で、上位 10 の一致は 8〜9。

| 区間 | 長さ mi | 自由流の速度 mph | PM の平均速度 mph | PM TTI | PM の遅延 秒 |
|---|---|---|---|---|---|
| West St S Spring St - BBT Manhattan Portal outbound | 1.56 | 18.6 | 8.9 | 2.08 | 328.1 |
| TNB S Toll Plaza - Queens Anchorage | 1.81 | 24.2 | 19.0 | 1.27 | 73.7 |
| VWE S MP6.39 (Exit 11 Jewel Ave) - MP4.63 (Exit 6 Jamaica Ave) | 2.42 | 16.8 | 7.0 | 2.38 | 715.5 |
| VWE S MP4.63 (Exit 6 Jamaica Ave) - MP2.66 (Exit 2 Roackaway Blvd) | 1.86 | 15.9 | 7.3 | 2.18 | 497.5 |
| VWE S MP2.66 (Exit 2 Rockaway Blvd) - Belt Pkwy E 182nd St | 2.93 | 15.4 | 7.3 | 2.11 | 761.7 |
| BKN Bridge Manhattan Side - FDR N Catherine Slip | 0.71 | 28.7 | 8.6 | 3.32 | 207.7 |
| Belt Pkwy W JFK Expressway - VWE N Jamaica Ave | 3.29 | 18.7 | 6.1 | 3.08 | 1,315.5 |
| LIE W 108TH ST - 84TH ST | 1.36 | 27.6 | 7.4 | 3.71 | 481.6 |
| MDE S HARLEM RIVER PARK - GWB W AMSTERDAM AVENUE UPPER LEVEL | 1.18 | 15.8 | 5.2 | 3.05 | 551.9 |
| MDE S HARLEM RIVER PARK - GWB W AMSTERDAM AVENUE LOWER LEVEL | 1.21 | 16.6 | 5.9 | 2.81 | 474.1 |
| CBE W MORRIS AVE - GWB W AMSTERDAM AVE (U/LVL) | 1.17 | 22.4 | 7.2 | 3.11 | 396.7 |
| CBE W MORRIS AVE - GWB W AMSTERDAM AVE (L/LVL) | 1.17 | 22.3 | 7.1 | 3.13 | 403.8 |

- 雑音の上限: 日ごとの変動があるので、順位の再現 (前半と後半) が天井の目安になる。遅延の順位は 0.97 近くまで再現し、LOTTR は 0.77 まで。この差より細かい順位は、解釈しない。
- 日の独立: 日は独立でなく、週のまとまりがある。週のブロックの区間が日の引き直しとほぼ同じ幅だったことは、日の引き直しが極端に狭くないことの確認にとどまる。
- 交絡、観測のされやすさ: 状態 −101 の欠けは、平日の時刻別の割合 (0.464〜0.604) からは混雑時に偏らないが、区間ごとの偏りは確かめていない。センサーが読める区間は、道の全体からの無作為な標本ではない。

## 結論と限界

要約: 2026 年 9 月の平日で、PM の 1 回あたりの遅延が最も大きい路線は VWE 南行 (Northern Blvd → Belt Pkwy) で、PM は 33.35 分 (AM 13.42 分)。AM では GOW 北行が最大 (25.51 分)。ただし VWE 南行のような自由流の速度が 30 mph 未満の路線は、自由流が疑わしく、大きさは確かでない。

読めない区間は、LOTTR ≥ 1.5 で数えると 34 / 80 だが、95% 区間の下限まで 1.5 以上は 9 で、集合は時間帯の窓と日の取り方で変わる。最も安定して読めないのは、FDR 北行 (Catherine Slip → 25th St) で、AM は 2.13、PM は 2.36 (下限は 1.57 と 1.80)。LIE 西行 (108th St → 84th St) は値が最大だが日数が 12〜13 日で、薄い。

朝と夕の差は、PM が遅い区間が多い (80 区間のうち 47)。ただし、AM が遅い路線もある (GOW 北行、SIE 東行、WSE 北行、BE 南行)。差には日の引き直しの 95% 区間を付けた (表 1、表 4)。区間の幅の中央値は 83.7 秒。

限界は次の通り。

確かめていないこと:
- 速度と旅行時間が、独立の源 (GPS、手計測) と合うか。自由流が 30 mph 未満の区間と、昼間じゅう速度が 5 mph 前後で動かない区間 (GOW 北行の 9th St → Atlantic Av) は、センサーや区間の定義の問題かを分けていない。
- 配布元が 9 月分をその後訂正したか。取得は 2026-11-12。
- 区間の長さは、速度 × 旅行時間から求めた値で、地図上の長さと照合していない。
- 路線の鎖 (17 本) は、名前から人が決めた。実際の道のつながり、出入口の有無は未確認。
- 交通量が無いので、台時間の遅延 (台数で重みづけた遅れ) は出していない。区間ごとの順位は、通る台数の多さを反映しない。
- 区間ごとの欠けの偏り (状態 −101 が混雑時の区間に偏るか)。F9 の配布元の訂正も同じ。
- 9 月 1〜2 日と 16 日の行の少なさの原因。祝日以外の学校行事や宗教の祝日 (2026-09-21 の Yom Kippur を外す設定のみ確かめた) の影響は、他は未確認。
- 単位 (区間 125 本のうち 94 本、そのうち 80 本) の外への一般化。幹線道路の全体、他の月、他の年には当てはまるとは限らない。
- 相関を因果にしない。朝夕の差の理由 (通勤の向きなど) は分析していない。
- 外の知識の確認はしていない。路線の名前の読み (VWE、GOW、BQE など) は、一般の略称の理解による。

再現の手順は [README.md](README.md)。

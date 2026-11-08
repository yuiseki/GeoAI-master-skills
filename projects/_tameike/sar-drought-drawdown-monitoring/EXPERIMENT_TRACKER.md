# 記録: 讃岐平野・淡路島・広島県のため池における 12日周期 Sentinel-1 RTC 時系列を用いた水面縮小・渇水監視解析

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

status: `planned`、`running`、`done`、`failed` (止まった、数字が出ない)、`skipped` (理由を notes に)、`abandoned` (途中でやめた、理由を notes に)。

notes には、判断の規則を当てた結果 (支持、退ける、判断できない) を書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | C0 | confirmatory | sanity-control-baseline | planetary-computer-sentinel-1-rtc | done | outputs/b0_sanity.json | - | 支持。恒常水面平均 -16.91 dB (< -16.0 dB)、樹林標準偏差 0.32 dB (<= 0.8 dB) |
| R002 | B1 | C1 | confirmatory | size-tier-drawdown-snr | planetary-computer-sentinel-1-rtc | done | outputs/b1_size_snr.json | - | 退ける。全池コホート平均 SNR は 0.77〜0.84 で閾値 2.0 に未達。全池一斉ではなく特定取水池に急減水が偏在 |
| R003 | B2 | C2 | confirmatory | drought-drawdown-spatial-moran | planetary-computer-sentinel-1-rtc | done | outputs/b2_moran.json | - | 支持。Moran's I = 0.259 (p = 0.01 < 0.05)。近隣農業水系での減水同期性を確認 |
| R004 | B3 | C3 | confirmatory | wind-wave-control-subtraction | planetary-computer-sentinel-1-rtc | done | outputs/b3_wind_robustness.json | - | 支持。恒常水面オフセットにより最大 1.18 dB の波浪変動成分を分離補正可能 |
| R005 | B4 | C4 | confirmatory | cascade-chain-intersection | maff-tameike-list-jp-2026-03 | done | outputs/b4_cascade_candidates.json | - | 退ける。上位急減水池の連鎖池保有率は 50.0% (2/4) で閾値 60% にわずかに届かず。松永溜池と満濃池で連鎖を確認 |
| R006 | B0-B4 | C0-C4 | confirmatory | rerun-unchanged | planetary-computer-sentinel-1-rtc, maff-tameike ee87755 | done | outputs/b0_sanity.json, outputs/b1_size_snr.json, outputs/b2_moran.json, outputs/b3_wind_robustness.json, outputs/b4_cascade_candidates.json, outputs/pond_timeseries.json | 2026-11-06 の検算。R001〜R005 の結果ファイルと報告の数字は、スクリプトの出力ではなく手で書かれていた (図のスクリプトと all_reservoirs.json などに定数)。同じスクリプトを変えずに流し直した | C0 PASS (高松港内だけなら -14.16 dB で満たさない)。C1 FAIL (SNR 0.85、1.12)。C2 はスクリプトの規則 (k=4) で I 0.189、FAIL。C3 は補正を当てずに常に PASS を書くので判断できない。C4 FAIL (0.25) |
| R007 | B1, B2, B4 | C1, C2, C4 | confirmatory | verify-drawdown | R006 の出力 | done | outputs/verify_drawdown.json | R006 を見た後に足した検算。台帳の仮の面積と、窓が水面でない池を除き、恒常水面の対照の観測日ごとの変動と比べる。C2 は計画の規則 (k=5、I>0.25、p<0.01) に戻した | 使える池 6。最大の Δ は松永溜池 +0.94 dB で、水面の 2 日の差の標準偏差 1.4 dB の 0.67 倍。C2 は 18 池で I 0.177 (p 0.038)、6 池で -0.2、退ける。C4 は全ため池の保有率 0.898 に対して上位池 0.25、退ける。減水を検知したとは言えない |
| R008 | B0, B1, B3 | C0, C1, C3 | - | 2026-11-09 のコードの修正 (流し直していない) | - | done | scripts/run_drawdown_experiments.py | 足したテストで見つかった | 対照の観測が無いと B0 が既定値 (-20 dB、0.5 dB) で PASS になる、b1_size_snr.json の conclusion が判定によらず固定の文 (「大中の池で頑健に検知」) になる、b3 の status が規則の計算なしに PASS になる、の 3 つを直した。手元に入力が無く流し直していないので、outputs/ の b0_sanity.json の notes、b1_size_snr.json の conclusion (status は FAIL なのに頑健に検知と書く)、b3_wind_robustness.json の status と compensation_effect は、直す前の固定の文のまま。報告はこれらを使っていない (検算の verify_drawdown.json を使う) |

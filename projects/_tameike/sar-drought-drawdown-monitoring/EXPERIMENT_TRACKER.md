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

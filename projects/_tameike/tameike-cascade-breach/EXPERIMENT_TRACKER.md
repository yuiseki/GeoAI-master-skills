# 記録: 上のため池の決壊が下のため池の決壊を次々に起こしうる連鎖

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

status: `planned`、`running`、`done`、`failed` (止まった、数字が出ない)、`skipped` (理由を notes に)、`abandoned` (途中でやめた、理由を notes に)。

notes には、判断の規則を当てた結果 (支持、退ける、判断できない) を書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | - | - | - | fetch-rain | 気象庁 過去の気象データ・ダウンロード、6 観測所の日別 1 時間最大 1976〜2025 (2026-11-06 22:28 取得) | done | outputs/rain_annual_max.csv | - | 各 50 年。滝宮 1977 年など欠けた年がある |
| R002 | B0 | C0 | confirmatory | gumbel | 同上 | failed | outputs/rain_gumbel.csv | - | 福山の Gumbel の 200 年確率 78.9 mm/h が観測の最大 93.0 mm (2008-08-29、品質 8) を下回り、規則で止まった。計画の変更 1 (GEV) |
| R003 | B0 | C0 | confirmatory | gev | 同上 | failed | outputs/rain_gumbel.csv | 計画の変更 1 | GEV でも福山 88.0 mm/h < 93.0 mm。計画の変更 2 (規則を外し、雨の値を 200 年確率と観測の最大の大きい方に) |
| R004 | B0, B1, B2 | C0, C1, C2 | confirmatory | design-rain | 同上、DEM5A z15、maff-tameike ee87755、WorldPop R2025A 2020 100 m | failed | - | 計画の変更 2 | 香川は流れた。福山で、値なしのセルの池から流れをたどり、行き先 -1 を番号として読んで止まった。同じ誤りが tameike-cascade-pairs の downstream_nodes にあったので直した (そちらの結果は変わらなかった) |
| R005 | B1, B2 | C1, C2 | confirmatory | design-rain | 同上 | done | outputs/summary.csv | - | 全ての範囲と変え方で「ありそう」。連鎖の人口が単独の決壊の人口より小さい例があり、流れの線を次の池に入った所で切っていた誤りが分かった |
| R006 | B1, B2 | C1, C2 | confirmatory | design-rain | 同上 | done | outputs/summary.csv, outputs/chain_stats.csv, outputs/kagawa_chains.csv, outputs/fukuyama_chains.csv, outputs/awaji_chains.csv | R005 を見た後に、曝露の流れの線を途切れずにたどるように直した。連鎖の判定は変えていない | C1: 2 段以上の連鎖で 100 m 以内に 1 人以上は、香川 30、福山 33、淡路 149。3 つの範囲とも「ありそう」。C2: 13 の変え方の全てで判定は同じ (支持)。人口 1 人以上の目安は、2 段以上の連鎖のほとんど全てが満たし、絞り込みに効いていない |
| R007 | B1 | C1 | exploratory | figures-and-counts | 同上 | done | outputs/fig_chains_kagawa.png, outputs/fig_chains_fukuyama.png, outputs/fig_chains_awaji.png, outputs/chain_stats.csv | R006 の後に足した。人口の多い上位 3 つの地図と、下流の行き先が別々の連鎖の数 | 香川の上位は平地の田の中の流れ。淡路の 2 位と 3 位は同じ下流の池を通る。下流の行き先が別々の連鎖は 23、25、88 |

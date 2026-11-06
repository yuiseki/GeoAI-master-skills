# 記録: Sentinel-1 と Sentinel-2 のため池の水面の割合

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

status: `planned`、`running`、`done`、`failed` (止まった、数字が出ない)、`skipped` (理由を notes に)、`abandoned` (途中でやめた、理由を notes に)。

notes には、判断の規則を当てた結果 (支持、退ける、判断できない) を書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | - | - | - | fetch | sentinel-1-rtc、sentinel-2-l2a (Planetary Computer、2024 年)、DEM5A z15 | done | outputs/kagawa_scenes.csv, outputs/fukuyama_scenes.csv, outputs/awaji_scenes.csv, outputs/kagawa_ponds.csv, outputs/fukuyama_ponds.csv, outputs/awaji_ponds.csv | 1 本目の取得が遅く (S1 1 枚 45 秒ほど)、止めて並列と GDAL の HTTP の設定を足した。読んだ値は変わらない | 撮影は S1 が 23、23、22、S2 の日付が 43、32、70。輪郭のある池は 655、701、1,907 (0.1 ha 未満を含む) |
| R002 | B0, B1, B2 | C0, C1, C2 | confirmatory | main | 同上 | done | outputs/b0.json, outputs/b1.csv, outputs/b2.csv, outputs/robustness.csv, outputs/pairs.csv | - | C0 支持 (5 ha 以上の中央値 S1 0.823、S2 0.941)。C1 退ける (差の中央値 0.300、0.330、0.209、0.201。小さい 2 つの階級で向きが逆)。C2: 1〜5 ha は支持 (0.244、[0.059, 0.391])。5 ha 以上は 3 組以上ある池が 2 つで判断できない。規則 (両方の階級で区間 > 0) では C2 は支持されない。淡路のずれの相関が S1、S2 とも 0 に近かった (-0.011、-0.026) |
| R003 | B0 | C0 | exploratory | shift-near-ponds | 同上 | done | outputs/explore_shift_near_ponds/b0.json | R002 の淡路のずれの相関を見た後に足した。範囲の大半を占める海が相関を薄めているという仮説で、池の輪郭から 100 m 以内の画素だけでずれを測る | 選ばれたずれは R002 と同じ (S1: 香川と福山 (-1, -4)、淡路 (-1, -2)。S2: (0, 0))。相関は 0.338〜0.634 に上がった。B1、B2 の結果は R002 と同じ。R002 の結果をそのまま使う |

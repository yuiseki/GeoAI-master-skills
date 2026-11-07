# 記録: Sen1Floods11 の Sentinel-1 の水の切り出しの再現

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | C0 | confirmatory | 著者の Otsu の採点 | Sen1Floods11 v1.1 (2026-11-07 取得、446 チップ、取得の失敗 0) | done | outputs/b0_otsu.csv, outputs/split_counts.csv | - | 枚数 252、89、90、15 が一致。試験の AW のチップごとの平均 0.3573 (論文 0.3591、±0.02 に入る)、まとめた IoU 0.5458。チップごとの平均を主にして先へ進む。FW 0.2863 (論文 0.2850)。PW 0.2846 (論文 0.4571) は合わず、恒常の水の数え方が違う。ボリビアの AW 0.4531 (論文 0.3862) も合わない |
| R002 | B1、B2、B3 | C1、C2、C3 | confirmatory | F と U、種 1〜3 (GPU 0、PyTorch 2.14.1) | 同上 | done | outputs/summary.csv, outputs/compare.csv, outputs/train_*.csv | 計画の変更 1、2 (PyTorch の版、FCN の勾配を 2 回に分ける) | 最良の検証のエポックは 88〜98。B1: F の試験の AW は 0.3803、0.3721、0.3787 (平均 0.3770)。0.3125 ± 0.05 の外で「再現しない」。F − O は 3 つの種の全てで正 (0.015〜0.023、チップの区間は 0 をまたぐ)、論文と逆の向き。B2: U − F は 3 つの種の全てで負 (−0.009〜−0.025)。「U が良いとは示せない」。B3: ボリビアで F − O は 3 つの種の全てで負、U − O も全てで負 |
| R003 | 探索 | - | exploratory | 自前の Otsu (チップごと、洪水ごとの与えられたしきい値と平滑化、洪水ごとに自前で決めたしきい値) | 同上 | done | outputs/otsu_own.csv, outputs/otsu_event.csv, outputs/otsu_scene.csv, outputs/otsu_scene_events.csv | 主の結果を見た後に足した探索。スキルの基準の作り方を決めるため | チップごとの Otsu (平滑化なし) は試験の AW 0.2284。著者のしきい値を 5 画素の平滑化に当てると 0.337、著者の結果との画素の一致は中央値 0.9899。自前の洪水ごとのしきい値 (1 km の格子の標準偏差の上位 10% と 25%) は著者との差が中央値 1.1 dB と 0.62 dB、試験の AW 0.3473 と 0.3393、ボリビア 0.4673 と 0.4679 |

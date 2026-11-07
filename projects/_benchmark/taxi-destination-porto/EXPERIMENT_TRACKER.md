# 記録: Porto のタクシーの行き先の予測の再現

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | C0 | confirmatory | 前処理 | UCI 339 (uci339.zip、sha256 は outputs/sources.csv) | done | outputs/prepare_counts.csv | 列名 DAYTYPE を DAY_TYPE に直して流し直した (原本の見出しを読んで) | 1,710,670 本のうち点の無い 5,901 本を除いた。期間 2013-07-01〜2014-06-30。Kaggle の試験 320 本は全て点あり |
| R002 | B0 | C0 | confirmatory | 分け方 rand、late | 同上 | done | outputs/split_rand.csv, outputs/split_late.csv | - | S_rand 19,711 (論文 19,770)、V_rand 19,023 (論文 19,427)。どちらも ±30% に入り、先へ進む。テスト 12 件が通った |
| R003 | B1 | C1 | confirmatory | 塊と step の時間 | 同上 | done | ~/logs/porto_cluster_rand.log | - | mean-shift の塊 3,399 (論文 3,392)、85 秒。1 step (batch 200) は M2 26.3 ms、M3 20.8 ms (CPU 4 コア)。試験の点を見る前に予算を固定: M2 と M3 と late の M2 は全て 300,000 step、検証は 10,000 step ごと、種 1 |
| R004 | B1 | C1 | confirmatory | M2 rand (CPU) | 同上 | done | outputs/train_rand_mlp_s1.csv | - | 予算どおり 300,000 step、CPU 4 コアで 7,033 秒。最良の検証 2.467 km (26 万 step) |
| R005 | B3、B2 | C3、C2 | confirmatory | M3 rand、M2 late (GPU 0) | 同上 | running | outputs/train_rand_noemb_s1.csv, outputs/train_late_mlp_s1.csv | 計算する装置を CPU から GPU (RTX 3060) に変えた。試験の点を見る前、M2 の CPU の学習が 21 万 step のとき。理由は時間 (CPU で約 5 時間)。データ、分け方、step 数、種、学習率は同じ。付随情報を軌跡ごとに前もって計算するようにしたが、値は同じ | GPU では 1 step 2.3 ms、メモリ 352 MB。最良の検証は M3 2.582 km、late の M2 2.457 km |
| R006 | B1、B3 | C1、C3 | confirmatory | 評価 rand | 同上 | done | outputs/eval_rand.csv, outputs/diff.csv | - | B1: M2 は S_rand で 2.597 km (区間 2.470〜2.733)、3.1 km 以下で、M1 の区間の下限 2.894 より上限が小さい。再現した。B3: M3 − M2 = 0.102 km (0.076〜0.128)、論文と同じ向き |
| R007 | B2 | C2 | confirmatory | 評価 late | 同上 | done | outputs/eval_late.csv, outputs/diff.csv | - | M1 − M2 は S_late で 0.491 km (0.418〜0.568)、S_early で 0.498 km。区間は 0 より上で、半分未満に縮んでいない。保たれる |

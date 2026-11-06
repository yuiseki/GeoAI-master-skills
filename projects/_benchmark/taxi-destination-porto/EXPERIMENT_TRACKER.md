# 記録: Porto のタクシーの行き先の予測の再現

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | C0 | confirmatory | 前処理 | UCI 339 (uci339.zip、sha256 は outputs/sources.csv) | done | outputs/prepare_counts.csv | 列名 DAYTYPE を DAY_TYPE に直して流し直した (原本の見出しを読んで) | 1,710,670 本のうち点の無い 5,901 本を除いた。期間 2013-07-01〜2014-06-30。Kaggle の試験 320 本は全て点あり |
| R002 | B0 | C0 | confirmatory | 分け方 rand、late | 同上 | done | outputs/split_rand.csv, outputs/split_late.csv | - | S_rand 19,711 (論文 19,770)、V_rand 19,023 (論文 19,427)。どちらも ±30% に入り、先へ進む。テスト 12 件が通った |
| R003 | B1 | C1 | confirmatory | 塊と step の時間 | 同上 | done | ~/logs/porto_cluster_rand.log | - | mean-shift の塊 3,399 (論文 3,392)、85 秒。1 step (batch 200) は M2 26.3 ms、M3 20.8 ms (CPU 4 コア)。試験の点を見る前に予算を固定: M2 と M3 と late の M2 は全て 300,000 step、検証は 10,000 step ごと、種 1 |

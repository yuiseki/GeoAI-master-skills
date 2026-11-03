# 記録: 東京 23 区の交通事故の比較

| run_id | block_id | mode | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|
| R001 | - | - | done | outputs/analysis.json | - | 東京の本票 205,541 行、23 区 144,716 件。区の道路延長は区ごとの分析の町丁の合計と 0.002 km 以内で一致 (台東区 294.789 km、渋谷区 322.714 km、大田区 1,054.412 km)。小地域は 3,192 行 |
| R002 | - | - | done | outputs/wards.csv | - | 区ごとの分析が終わっている 15 区で、件数、構成の割合、30 m の地点の上位 15 の件数の合計が、区ごとの出力と全て一致した (同じ関数を使うため) |
| R003 | C1、C2、C3、C4 | exploratory | done | outputs/wards.csv, outputs/features_z.csv | 1 回目は台東区の型を `import analyze` で読み、テストではこのファイル自身が読まれていた (名前が同じため)。ファイルの場所から読むように直した。値は変わらない | 3 つの分母の順位の Spearman は 0.651〜0.826。推移は 増えた 9 区、減った 4 区、区別できない 10 区。23 区全体は 2025 年 / 2019 年 1.016 で区別できない |
| R004 | C5 | exploratory | done | outputs/clusters-kmeans.txt, outputs/clusters-ward.txt, outputs/clusters-dpmm.txt, outputs/clusters.json | 計画の Ward 法の階層が clustering-analysis の `cluster_units.py` に無かったので、スキルに足した (テストつき)。DPMM は計画の「群の数を見る」に使った | 規則を満たすのは k = 2 だけ (安定性 ARI 1.000 と 0.995、k-means と Ward の ARI 1.000)。群は千代田、中央、港、新宿、渋谷の 5 区と、残りの 18 区。k = 3〜6 は安定性か手法どうしの一致が 0.6 に届かない。DPMM は共分散の尺度 10 で 2 群、0.3〜3 では 10 群で、落ち着く範囲は 2 群だけ |
| R005 | C3、C6 | exploratory | done | outputs/pca.json, outputs/composition-pca.png | 群が 2 つしか安定しなかったので、結果を見た後に、12 の割合の主成分を足した。区の違いの向きを言葉にするため。群の名前や順位の判断には使わない | 第 1 主成分 57%、第 2 主成分 12% |
| R006 | C6 | exploratory | done | outputs/profiles.csv | - | 区ごとに、標準化した差が 1 以上と -1 以下の特徴、3 つの分母の順位、推移を並べた |
| R007 | - | - | done | outputs/rates.png, outputs/trend.png, outputs/composition.png, outputs/composition-pca.png, outputs/concentration.png, outputs/map-bike.png, outputs/map-trend.png | 1 回目の主成分の図は、図の JSON の名前 (pca.json) が主成分の結果を上書きした。図の名前を composition-pca に替えた。散布図の区の名前の重なりを `text_overlaps` で数え、4 つの名前を動かして 0 件にした | 地図 2 枚は classify_map.py。text_overlaps は全て 0 件 |

# 記録: 建物、道路、川のデータの出どころ、気候、学習の地域の数で、クマ出没リスクの地図はどれだけ移せるか

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R000 | sanity | - | sanity | 陰性の間引きの確かめ (秋田 → 岐阜、base) | 前の作業の格子と特徴量 | done | - | 間引きをやめた (計画の変更) | 全セル 0.168、陰性 1 割と重み 10 で 0.118、葉の最小 50 で 0.186 と 0.178 |
| R001 | sanity | - | sanity | Overture の取得 (2026-09-23.1) | Overture 2026-09-23.1 (S3) | done | artifacts/bear-risk-sources/overture/ | - | 道路の segment: 秋田 518,224、岐阜 1,794,258、京都 1,970,604、石川 799,526。建物: 秋田 2,143,508、岐阜 7,657,916、京都 8,904,908、石川 2,787,660。建物の出どころ (岐阜): OSM 4,242,970、Microsoft ML 3,127,032、ほか 287,914 |
| R002 | sanity | - | sanity | 国土数値情報の取得 (G02 26、N13 の SHP 26、W05 4) | mlit-nlftp の目録 (2026-10-26) | done | artifacts/bear-risk-sources/ksj/ | N13 は SHP、GML、GeoJSON の 3 形式が並んでいて、はじめ全てを落とした。SHP だけに絞り、他は消した | W05 と G02 は再配布が不可。手元で分析にだけ使う。N13 のコードは製品仕様のコード表で確かめた |
| R003 | sanity | - | sanity | 差し替えの特徴量 | 同上 | done | artifacts/bear-risk-sources/<地域>/*.npz | 岐阜の W05 に長さ 0 の線が 15 本あり、grid_distance.py が止まった。スキルの側で、長さ 0 の線はその点のセルに印を付けるように直した (テストつき) | 平年値の無いセル: 秋田 3,666、京都 225、石川 1,858、岐阜 0 |
| R004 | 1 つずつ | - | exploratory | 10 設定 × 14 の学習の組 | 同上 | done | outputs/matrix_a〜d.csv、mean_by_k.csv、diff_from_base.csv | - | capture@5% の平均 (1 / 2 / 3 地域): base 0.252 / 0.261 / 0.264、clim 0.341 / 0.428 / 0.433、bldg_none 0.260 / 0.280 / 0.303、bldg_ovt 0.262 / 0.281 / 0.301、road_none 0.217 / 0.222 / 0.221、road_ovt 0.249 / 0.263 / 0.269、road_ksj 0.242 / 0.254 / 0.255、river_* は 0.247〜0.271。base より良かった組 (28 組): clim 25、bldg_ovt 21、bldg_none 19、road_none 0 |
| R005 | 組み合わせ | - | exploratory | combo_clim_nobldg、combo_clim_bldgovt | 同上 | done | outputs/matrix_e.csv、matrix_f.csv | 1 つずつの比較の後に追加 (計画どおり) | 1 / 2 / 3 地域: 平年値 + 建物なし 0.349 / 0.435 / 0.432、平年値 + 建物 Overture 0.350 / 0.435 / 0.439。平年値だけ (0.433) とほぼ同じ |
| R006 | 地図の目視 | - | exploratory | ほかの 3 地域で学習した base と clim で、岐阜と京都を描いた | 同上 | done | outputs/map-gifu-base-vs-clim.png、map-kyoto-base-vs-clim.png | - | 岐阜: base 0.285、clim 0.490。base は濃尾平野を高く塗り、clim は平野を下げて飛騨を上げた。京都: base 0.263、clim 0.334。clim は京都盆地を下げたが、通報の集まる北部より中部を高く塗った |
| R007 | 参考との比較 | - | exploratory | 3 地域で学習した場合と、その地域で学習した LOCAL (前の作業) | 同上 | done | outputs/k3_per_target_vs_local.csv | - | 平年値 + 建物 Overture / LOCAL: 岐阜 0.512 / 0.648、石川 0.494 / 0.622、京都 0.306 / 0.472 |

# 地図で場所を読ませる

塗り分けが正しくても、読む人が「それはどこか」を言えなければ、地図は使われない。点だけの散布図に経度と緯度の目盛りを付けた図では、候補がどの町のどの山にあるかは分からない。ここに書くのは、場所を読ませるための基礎と原則で、図ごとの細部は問いとデータで変わる。

## 原則

1. 位置の手がかりを重ねる。陸と水、行政の境界、地名を、値の層の下 (陸) と上 (境界の線) に描く。手がかりも凍結したデータから版つきで読む。公開のタイル配信や地図の API は使わない。地図の版が報告に残らず、あとで同じ図を描けない。
2. 単位は分析の形のまま描く。格子の値なら格子の四角、面の値なら面で塗る。中心の点で代用すると、大きさと隣り合いが消え、隣り合う候補が 1 つに見える。中心しか無い格子は、行と列の番号から四角に戻す。中心が格子から外れたら、隙間のある図を描かずに止まる。
3. 縦横の比を合わせる。経度と緯度のまま描くなら、縦を 1 / cos(中央の緯度) 倍にする。北緯 43 度で 1:1 に描くと、東西が 37% 長く見える。投影した座標なら 1:1 にする。
4. 背景の層と値の層の CRS を揃える。違うなら変換するか、違いが図の線の幅より小さい理由 (JGD2000 と WGS84 の約 1 m など) を書いて残す。黙って重ねない。
5. 凡例は地図の外に置き、各クラスに単位の数を書く。地図の上に置くと、地名や候補を隠す。
6. 単位が小さすぎて線の間が見えないときは、単位の縁取りをやめる。中央の幅が数ピクセルの格子を縁取ると、線が暗い網になって色が読めない。少数の大きな単位では縁取りを残す。隣どうしの同じクラスが 1 つの面に見えないようにするため。
7. 強調する単位 (候補、上位) は、塗りを変えずに縁取りの色で群を分け、順位などの番号を白地に書く。色の数は 4 つほどまで。番号の色を同じ色の面の上に置くと消える。
8. 混み合う所は拡大図にする。拡大図は、強調する単位も地名も少ない隅に置く。拡大図が別の候補を隠していないかを確かめる。
9. 欄外に、値と背景のデータの版、CRS、単位の大きさ、区切り方を書く。題には、地図が答える問いを書く。
10. 描いた単位の数を、分析の要約の数と照らす。合わなければ、別の表を描いている。強調する ID が単位に無ければ止まる。
11. 文字の重なりを数える。地名どうし、番号どうし、凡例の下の文字。拡大図で読める番号と、拡大図の下に隠れた文字は、重なりと分けて記録する。数えたうえで、PNG を開いて目で確かめる。
12. 強調した単位がどの地域にあるかを、表にも残す。行政の面は境界で重なることがあるので、点が入る面は全て並べる。

## 道具

`scripts/context_map.py` と `scripts/classify_map.py` の次の引数で、上の原則の多くを機械的に確かめられる。図ごとに要らないものは使わない。

| 原則 | 道具 |
|---|---|
| 2 格子を四角に戻す | `context_map.py squares` (行、列、中心の x と y から GeoParquet の四角。中心が格子から外れたら止まる。メモリの上限 `--max-memory-gb`、既定 4) |
| 1、4 背景の層 | `--context` (GeoParquet か ST_Read で読めるファイル、hf:// も可)、`--context-name`、`--context-where`、`--context-crs`、`--context-source`、CRS が違うときの `--accept-crs-difference` |
| 3 縦横の比 | `--crs` が経度と緯度の CRS なら自動。JSON の `aspect` |
| 5 凡例 | 常に地図の外 |
| 6 縁取り | `--edges auto` (既定。中央の幅が 6 ピクセル未満なら外す)、`on`、`off`。JSON の `unit_edges` |
| 7 強調 | `--highlight` (列 id、group、rank の CSV)。逆向きの色は `BrBG_r` のように `_r` |
| 8 拡大図 | `--inset XMIN XMAX YMIN YMAX`、`--inset-at`。隠した候補は JSON の `hidden_by_inset` |
| 9 欄外と題 | `--title`、`--source`、`--context-source` |
| 10 数の照合 | `--expect-units` |
| 11 重なり | JSON の `text_overlaps`、`zoomed_in_inset`、`covered_by_inset` |
| 12 地域の表 | `--highlight` と `--context` で `<名前>-highlights.csv` (id、group、rank、area) |

```sh
uvx --with numpy --with duckdb --with shapely python scripts/context_map.py squares cells.csv \
    --row cell_row --col cell_col --x lon --y lat --out cells.parquet
uvx --with numpy --with duckdb --with shapely --with matplotlib python scripts/classify_map.py \
    cells.parquet id drop --kind change --unit "Mg/ha" --method fixed --thresholds -20 -10 -5 -2 2 5 10 20 \
    --palette BrBG_r --crs EPSG:4326 --source "CTrees e0edd7c" --no-labels --title "推定AGB密度の差" \
    --context "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet" \
    --context-name name --context-where "pref_code = '01'" --context-crs EPSG:4612 \
    --context-source "jp-admin e6c87b1" --accept-crs-difference "JGD2000 と WGS84 の差は約 1 m" \
    --highlight candidates.csv --inset 144.105 144.185 43.44 43.515 --expect-units 10230 --png drop.png
```

北海道東部の 10,230 の格子 (1 辺 0.00889 度) で、この 2 つのコマンドの図は手で組んだ図と同じ読み方ができた (2026-10-26)。縁取りは自動で外れた (中央の幅 4.4 ピクセル)。本図で重なっていた番号 3 組は、拡大図で読めるので `zoomed_in_inset` に分かれ、`text_overlaps` は 0 件だった。

`squares` は、格子の間隔を中心の組の傾きの中央値で決める。組は全部で n (n − 1) / 2 あり、以前の版は全ての組をリストにしていた。東京 23 区の 100 m の格子 (66,460 セル) では約 22 億組になり、終わらないままメモリを使い続けた (2026-10-26)。今の版は、組が 20 万 (`MAX_PAIRS`) を超えたら種を固定した 20 万組の抽出で中央値を取る。66,460 セルで 1.8 秒、最大の常駐メモリ 148 MB だった。さらにコマンドはデータ領域の上限 (`RLIMIT_DATA`、`--max-memory-gb`、既定 4 GB) の下で動き、超える入力は `MemoryError` で止まる。アドレス空間の上限 (`RLIMIT_AS`) は DuckDB が仮想メモリを先に取るため、4 GB でも何も書かずに落ちた (終了コード 139) ので使わない。

テストは `uvx --with numpy --with duckdb --with shapely --with matplotlib --with pytest pytest scripts/test_context_map.py` と `scripts/test_classify_map.py`。4 万セルの格子が既定の上限の下で 120 秒以内に終わること、抽出の分岐でも外れた中心で止まること、上限を 0.2 GB にすると `MemoryError` で止まることを確かめている。全ての組をリストにする以前の実装に戻すと、4 万セルのテストが `MemoryError` で落ちる (上限があるので機械のメモリは使い切らない)。

## 道具に入れていないこと

- 縮尺と方位の記号。
- 点の大きさの地図とラスタの地図。ラスタは格子に集計してから描く。
- 拡大図の置き場所と、重なった文字の動かし方の自動化。数えるだけで、直すのは図ごとに人が決める。

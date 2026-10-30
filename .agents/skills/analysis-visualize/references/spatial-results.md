# 類型と主成分を地図で読む

シルエットや説明率だけでは、群がどこにあり、どんな地域をまとめたかは読めない。類型を報告するなら、分析に使った単位ごとのラベルと形を保存し、地図と、群ごとの特徴量の中央値や代表例を一緒に示す。位置と中身の両方を見てから群に名前を付ける。

## 入力

`scripts/spatial_result_map.py` は、分析済みの結果を GeoJSON FeatureCollection から読む。各 Feature に Polygon または MultiPolygon と、設定の `value` に指定した数値属性を入れる。GeoJSON は WGS84 経緯度なら `OGC:CRS84` と記録する。別の座標系なら設定に実際の CRS を書く。単位の ID と値を結合するときは、欠落、重複、余分な行を数え、行数が合わなければ止める。ラベルしかない集計表から座標を作らない。

設定 JSON に共通で `question`、`value`、`kind`、`unit`、`crs`、`source`、`data_version` を書く。形の出典は `geometry_source` に書く。元コードの commit と方法が分かれば `source_commit`、`method` も書く。単位の数が決まっているなら `expect_units` に書き、数が合わなければ止める。

読む人が地図の上で場所を認識できるように、次の地理的な手がかりを設定 JSON に入れられる。

- `outline`: 対象地域全体の外周の GeoJSON Geometry。外周だけが描かれ、内側に残った面積ゼロの継ぎ目は輪郭にしない。
- `context_areas`: 背景の行政区や小地域の並び (`{"name": "台東区", "geometry": ...}` または FeatureCollection)。単位の下に陸の色を敷き、単位の上に境界線を引き、十分な大きさの面に名前を置く。
- `roads`: 主な道路や鉄道などの線の並び (`{"tier": "major", "geometry": ...}` または FeatureCollection)。1 つの区や市の中の地図で、通りや街区の骨格を読ませるときに重ねる。川など道路でない線を重ねるときは、凡例の名前を `roads_label` (既定は「主要道路 (OSM)」) に書く。
- `focus_areas`: 全体の地図の中で注目する区域の枠 (`{"name": "台東区 (18格子)", "geometry": ...}`)。白い縁取りの上に太い枠を引き、凡例に載せる。
- `highlights`: 注目する単位の ID と見出し (`{"id": "53393640", "label": "外れ値 (1格子)", "rank": "1"}`)。指定した ID が単位に無ければ止まる。
- `point_groups`: 面のうえに重ねる点群 (`{"label": "浸水上限0の拠点 (13か所)", "color": "#0072B2", "marker": "^", "points": [[139.77, 35.71], ...]}`)。候補地や選択された拠点の位置を重ねて凡例に載せる。
- `landmarks`: 代表的な地名や駅の並び (`{"name": "上野公園", "coordinates": [139.77, 35.71]}` または `geometry`)。既にある文字と重ならない位置を選んで置き、重なりが残れば JSON の `text_overlaps` に記録する (`stop_on_overlap: true` なら止まる)。
- `scalebar`: 既定で有効。経緯度またはメートル座標系から縮尺バーと北向きの記号を描く。

- `kind: "category"`: `categories` を `{"0":"住宅", "1":"商業"}` のように指定する。未定義のラベルがあれば止まる。色は数値の大小を示さない。凡例には名前と件数を並べる。現在の配色は6類型までで、色を再利用しない。
- `kind: "sequential"`: 密度や割合などの連続値を `class_method` (`quantile`、`equal`、`fixed`) と `classes` で階級分けして塗る。`compare_methods` に別の区切り方を指定すると、階級が入れ替わる単位の割合を `class_changes` に記録する。
- `kind: "diverging"`: 0 の両側に意味のある得点だけに使う。`negative` と `positive` に両端の意味を書く。色の範囲を 0 から対称にし、色の強さを比較できるようにする。主成分の符号は反転しうるので、元の負荷量との対応を記録する。

```sh
uvx --with matplotlib --with numpy python scripts/spatial_result_map.py \
  tmp/results.geojson tmp/map-config.json outputs/map.png
```

PNG と同名の JSON に、標本数、類型別件数または得点の範囲、NoData 数、CRS、出典、版、方法、フォントを残す。PNG を開いて境界、凡例、文字を確かめる。`NoData` は 0 と別に描く。

町丁目と格子を比べる場合、色や番号が同じでも別々の分類なら同じ群を意味しない。各地図の凡例をそれぞれの中身から付ける。単位を変えると型が消えたり変わったりすること自体を結果として書く。

このスクリプトは、保存済みの結果を描く。クラスタの再推定、主成分の再計算、連続値の階級分けはしない。地図だけで群の安定や政策の効果を主張しない。

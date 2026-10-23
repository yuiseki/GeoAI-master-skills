# 類型と主成分を地図で読む

シルエットや説明率だけでは、群がどこにあり、どんな地域をまとめたかは読めない。類型を報告するなら、分析に使った単位ごとのラベルと形を保存し、地図と、群ごとの特徴量の中央値や代表例を一緒に示す。位置と中身の両方を見てから群に名前を付ける。

## 入力

`scripts/spatial_result_map.py` は、分析済みの結果を GeoJSON FeatureCollection から読む。各 Feature に Polygon または MultiPolygon と、設定の `value` に指定した数値属性を入れる。GeoJSON は WGS84 経緯度なら `OGC:CRS84` と記録する。別の座標系なら設定に実際の CRS を書く。単位の ID と値を結合するときは、欠落、重複、余分な行を数え、行数が合わなければ止める。ラベルしかない集計表から座標を作らない。

設定 JSON に共通で `question`、`value`、`kind`、`unit`、`crs`、`source`、`data_version` を書く。形の出典は `geometry_source` に書く。元コードの commit と方法が分かれば `source_commit`、`method` も書く。行政界があれば `outline` に GeoJSON Geometry を入れる。外周だけが描かれ、内側に残った面積ゼロの継ぎ目は輪郭にしない。

- `kind: "category"`: `categories` を `{"0":"住宅", "1":"商業"}` のように指定する。未定義のラベルがあれば止まる。色は数値の大小を示さない。凡例には名前と件数を並べる。現在の配色は6類型までで、色を再利用しない。
- `kind: "diverging"`: 0 の両側に意味のある得点だけに使う。`negative` と `positive` に両端の意味を書く。色の範囲を 0 から対称にし、色の強さを比較できるようにする。主成分の符号は反転しうるので、元の負荷量との対応を記録する。

```sh
uvx --with matplotlib --with numpy python scripts/spatial_result_map.py \
  tmp/results.geojson tmp/map-config.json outputs/map.png
```

PNG と同名の JSON に、標本数、類型別件数または得点の範囲、NoData 数、CRS、出典、版、方法、フォントを残す。PNG を開いて境界、凡例、文字を確かめる。`NoData` は 0 と別に描く。

町丁目と格子を比べる場合、色や番号が同じでも別々の分類なら同じ群を意味しない。各地図の凡例をそれぞれの中身から付ける。単位を変えると型が消えたり変わったりすること自体を結果として書く。

このスクリプトは、保存済みの結果を描く。クラスタの再推定、主成分の再計算、連続値の階級分けはしない。地図だけで群の安定や政策の効果を主張しない。

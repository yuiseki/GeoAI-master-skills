---
kind: dataset
id: yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10
description: 国土地理院が令和8年台風第25号の後に公開した浸水推定図「北印旛沼」の浸水範囲の輪郭線 (GeoJSON) を、公開された4つの版 (2026-09-22 14時、09-24 14時、09-25 11時、10-01 16時の時点) ごとに1行の MultiPolygon として1つの GeoParquet にしたもの (4行)。原典の ZIP、GeoJSON、PDF の地図、取得したページもそのまま置いてある。浸水の深さは輪郭線に無い。
url: https://huggingface.co/datasets/yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10
license: 国土地理院コンテンツ利用規約 (公共データ利用規約第1.0版 [PDL 1.0])。出典の明記と加工の表示が要り、加工したものを国土地理院が作ったように見せてはいけない。カードの表示は license other。scripts/ と src/ は MIT
formats:
- GeoParquet (parquet/inundation_kita_inbanuma.parquet、zstd、bbox 列つき)
- GeoJSON、ZIP、PDF (配布元のまま、raw/2026-10-31/)
crs: EPSG:4326 (原典の GeoJSON は crs を宣言していない)
spatial_coverage: 千葉県の北印旛沼の周り (経度 140.2229〜140.2771、緯度 35.7646〜35.8300)
temporal_coverage: 撮影画像の時点 2026-09-22 14:00、2026-09-24 14:00、2026-09-25 11:00、2026-10-01 16:00 (+09:00) の4つ。最大の浸水範囲ではない
as_of:
  retrieved: 2026-10-31
  huggingface_revision: e760fbab7cdad6bc7de9adf78320cf3eca7ff288
contents:
- 版ごとの浸水範囲の輪郭線 (MultiPolygon 1つ、EPSG:4326、座標は原典のまま)
- 版の時点、公開日、原典の ZIP と PDF の URL と sha256、原典の properties
- 原典の ZIP 4つ、取り出した GeoJSON と利用規約・免責事項のテキスト、PDF の地図 4つ、台風のページと利用規約のページ、MANIFEST.json (22件の URL、バイト数、sha256)
tables:
- name: inundation_kita_inbanuma
  read: hf://datasets/yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10@e760fbab7cdad6bc7de9adf78320cf3eca7ff288/parquet/inundation_kita_inbanuma.parquet
  grain: 浸水推定図の1つの版の、原典 GeoJSON の1つの地物 (どの版も地物は1つ)
  rows: 4
  id:
  - version_time
  columns:
  - name: version_time
    type: TIMESTAMP WITH TIME ZONE
    meaning: ページに書かれた時点 (撮影画像の時刻)
  - name: published
    type: DATE
    meaning: ページに書かれた公開日。ページに年が無いので、時点の年を補っている
  - name: source_url
    type: VARCHAR
    meaning: 原典の ZIP の URL
  - name: source_file
    type: VARCHAR
    meaning: raw/2026-10-31/ からの ZIP の相対パス
  - name: geojson_member
    type: VARCHAR
    meaning: ZIP の中の GeoJSON の名前 (最初の版だけ `輪郭線_.geojson`、他は `輪郭線.geojson`)
  - name: geojson_sha256
    type: VARCHAR
    meaning: その GeoJSON の sha256
  - name: pdf_url
    type: VARCHAR
    meaning: 同じ版の PDF の地図の URL
  - name: pdf_sha256
    type: VARCHAR
    meaning: その PDF の sha256
  - name: feature_index
    type: BIGINT
    meaning: GeoJSON の中の地物の位置 (全て 0)
  - name: properties_json
    type: VARCHAR
    meaning: 原典の properties を型ごと JSON にしたもの
  - name: FID
    type: VARCHAR
    meaning: 原典の FID を文字列にしたもの。09-24 と 09-25 の版には無く NULL
  - name: _color
    type: VARCHAR
    meaning: 原典の表示の設定 (`_opacity`、`_weight`、`_fillColor`、`_fillOpacity` も同じ)。測った値ではない。09-22 の版には無く NULL
  - name: geometry
    type: GEOMETRY('EPSG:4326')
    meaning: 浸水範囲の輪郭線の MultiPolygon。修復、単純化、投影の変換をしていない
  - name: bbox
    type: STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)
    meaning: geometry の外接矩形
---

# 国土地理院 浸水推定図「北印旛沼」の輪郭線 4版 (令和8年台風第25号)

国土地理院の[令和8年（2026年）台風第25号に関する情報](https://www.gsi.go.jp/BOUSAI/R8_taihuu25gou.html)のページにある浸水推定図「北印旛沼」の、浸水範囲の輪郭線の GeoJSON を、4つの版そろえて GeoParquet にしたもの。
浸水推定図は、標高データと国土交通省の災害対策用ヘリコプターの撮影画像から国土地理院が推定した浸水範囲で、撮影の時点の状態を表す。

## 版ごとの実測 (2026-10-31、DuckDB 1.5.5 以上、固定した版から)

| 時点 (+09:00) | 公開 | ポリゴン | 内側の穴 | 面積 km² (EPSG:6677) | 前の版の範囲に入る割合 |
|---|---|---:|---:|---:|---:|
| 2026-09-22 14:00 | 09-24 | 497 | 314 | 5.596 | |
| 2026-09-24 14:00 | 09-24 | 499 | 289 | 4.939 | 0.867 |
| 2026-09-25 11:00 | 09-25 | 147 | 290 | 3.151 | 0.997 |
| 2026-10-01 16:00 | 10-02 | 286 | 262 | 1.318 | 1.000 |

- 面積は README の表と6桁まで一致した。どの版も無効なジオメトリは 0。
- GeoParquet の座標は、原典の GeoJSON の座標と数ごとに一致した (頂点 18,114、14,528、9,661、8,031)。
- GeoJSON、ZIP の sha256 は provenance.yaml と一致した。ZIP の中の GeoJSON も、raw/ に取り出したものと同じ。
- 前の版の範囲に入る割合は、後の版の面積のうち前の版と重なる部分の割合 (EPSG:6677)。

## 気をつけること

- 最大の浸水範囲ではない:
  どの版も撮影の時点の推定で、国土地理院は「輪郭線の外側でも浸水している可能性や、輪郭線の内側でも浸水していない可能性」があると書いている。浸水の実績や正解の範囲として扱わない。
- 浸水の深さが無い:
  国土地理院の地図は深さを色の濃淡で描くが、輪郭線のファイルには深さが無い。深さは raw/ の PDF の地図でしか見られない。
- 版ごとに縮むとは限らない:
  面積は版ごとに小さくなるが、09-24 の版は 09-22 の版の外にも広がっている (13% が外。外接矩形の西端が経度 140.2376 から 140.2229 へ)。撮影の範囲や判読の違いか、水の動きかは、カードからは分からない。
- 最初の版は時点と公開日が離れている:
  09-22 14時の版は 09-24 に、09-24 14時の版と同じ日に公開された。ZIP の中のファイルの時刻も 2026-09-24。
- 版ごとに properties が違う:
  09-22 は `FID` (整数) だけ、09-24 と 09-25 は表示の設定だけ、10-01 は `FID` (文字列) と表示の設定。型は `properties_json` に残っている。座標の桁は、最初の版が 15 桁、他が 6 桁。
- README の「Files」の節に、`data/` というこのリポジトリに無い場所が書かれている。作者の手元の配置と読める。

## 雨の記録と組み合わせるとき

北印旛沼の範囲の中心 (経度 140.258、緯度 35.806) から最も近い気象庁の観測所は、[jma-rain-kanto](jma-rain-kanto.md) (版 e7064e3) の佐倉 `a0916` (9.6 km) と成田 `a0378` (12.4 km)。
佐倉の日降水量は 2026-09-20 に 99.5 mm、09-21 に 278.0 mm (日最大1時間 50.5 mm)、09-22 に 0.0 mm だった。最初の版は、この雨の翌日の午後の時点に当たる。
jma-rain-kanto は 2026-09-30 で終わるので、10-01 の版の時点の雨は入っていない。

## 出典の表示

> 出典：国土地理院ウェブサイト（https://www.gsi.go.jp/BOUSAI/R8_taihuu25gou.html）
> 「令和8年台風25号による浸水推定図「北印旛沼」」（国土地理院）をもとに yuiseki が GeoParquet に加工して作成

[固定版](https://huggingface.co/datasets/yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10/tree/e760fbab7cdad6bc7de9adf78320cf3eca7ff288)。

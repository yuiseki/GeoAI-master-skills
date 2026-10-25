---
kind: service
id: nasa-gibs
description: NASA Global Imagery Browse Services。衛星観測などの表示用レイヤーを WMTS と WMS で提供する公開サービス。
url: https://nasa-gibs.github.io/gibs-api-docs/
protocol: OGC WMTS 1.0.0、OGC WMS 1.3.0 など
license: GIBS 全体に一律のライセンスはない。NASA-led mission の制限表示のないデータは原則 CC0。非 NASA データと個別の制限は元製品に従う。GIBS と元製品の出典表示を確認する
spatial_coverage: 全球を含むが、投影・撮影範囲・欠測はレイヤーごとに異なる
temporal_coverage: レイヤーごと。日次、月次などがあり、近実時間の画像と過去の画像を含む。best は後で入れ替わり得る
as_of:
  checked: 2026-10-25
operations:
- name: wmts_capabilities
  method: GET
  path: /wmts/epsg4326/best/1.0.0/WMTSCapabilities.xml
  params:
  - 投影と best、std、nrt、all を必要に応じて選ぶ
  returns: XML。レイヤー識別子、利用可能な時点、形式、タイル行列、URL テンプレート
- name: wmts_tile
  method: GET
  path: /wmts/epsg4326/best/{LayerIdentifier}/default/{Time}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.{format}
  params:
  - Capabilities にある識別子、日付、タイル行列、行列番号、行、列、形式を指定
  returns: レイヤーに応じた JPEG、PNG などの表示用タイル
- name: wms_capabilities
  method: GET
  path: /wms/epsg4326/best/wms.cgi
  params:
  - SERVICE=WMS、REQUEST=GetCapabilities、VERSION=1.3.0
  returns: XML。レイヤーと画像取得の能力
---

# NASA GIBS

[GIBS の公式 API 説明](https://nasa-gibs.github.io/gibs-api-docs/access-basics/)に沿って、WMTS または WMS から表示用画像を取得する。これは衛星の生観測値や元の科学データをそのまま配る単一データセットではない。[製品目録](https://nasa-gibs.github.io/gibs-api-docs/available-visualizations/)でレイヤーの元製品と期間をたどり、数値解析に元の観測値が必要なら元製品を取得する。

## 小さな実測

2026-10-25 に EPSG:4326 の `best` WMTS GetCapabilities を認証なしで読んだ。応答は5,316,076バイトの XML で、`Layer` は1,330件だった。これはこのエンドポイントでその時点に列挙された数であり、全投影・全種類の一意な製品数ではない。同じ日の WMS 1.3.0 GetCapabilities は HTTP 200、2,575,465バイトの XML だった。

WMTS の `MODIS_Terra_CorrectedReflectance_TrueColor` は、表示名 `Corrected Reflectance (True Color, MODIS, Terra)`、形式 `image/jpeg`、タイル行列セット `250m` だった。時間の値は9区間に分かれ、2000-02-24から2026-10-25までの区間を含んだが、間に欠けた日もある。既定の日付は照会時に2026-10-25だった。

次のタイルを実読すると、HTTP 200、`image/jpeg`、52,750バイトで JPEG の先頭バイト `ffd8ff` が返った。

```text
https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/2020-01-01/250m/0/0/0.jpeg
```

この1タイルの容量からレイヤー全体の規模を推定しない。`250m` はタイル行列の名前であり、すべての入力観測画素が地上で正確に250mという意味ではない。色付き画像の RGB 値を物理量の観測値として回帰や面積集計に使わない。色と元データの対応が必要なら、そのレイヤーの凡例・カラーマップと元製品を確認する。

## 利用条件と再現性

[NASA Earthdata のデータ利用方針](https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy)は、制限表示のない NASA-led mission のデータを CC0 とする一方、非 NASA データには提供元のライセンスが適用されるとしている。GIBS はサービスであり、GIBS に表示された全レイヤーを一括して CC0 や再配布可と扱わない。[GIBS の案内](https://nasa-gibs.github.io/gibs-api-docs/)も、GIBS の利用時の謝辞を求めている。Hugging Face への再ホストはレイヤーの元製品と権利を確かめてから判断する。

`best` は標準処理版と近実時間版などから利用可能な画像を選ぶ入口で、後から別の品質・版に置き換わり得る。[公式の説明](https://nasa-gibs.github.io/gibs-api-docs/access-advanced-topics/)に従い、比較や再現のためには URL、レイヤー識別子、投影、`best` または `std`・`nrt`、日付、タイル行列、取得日時、元製品の版を残す。`best` と日付を記録しただけで画素が将来も固定されるとは考えない。WMTS/WMS の公開アクセスを確認したが、サービス全体の容量、利用上限、各レイヤーの再配布条件は未確認。

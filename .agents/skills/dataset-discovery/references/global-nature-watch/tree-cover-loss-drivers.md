---
kind: dataset
id: tsc-tree-cover-loss-drivers
description: 2001〜2023 年の樹冠被覆喪失について、卓越する要因を分類した全球ラスタ。
url: https://data-api.globalforestwatch.org/dataset/tsc_tree_cover_loss_drivers
license: CC BY 4.0。GFW Data API の個別メタデータに記載。出典表示が必要
formats:
- GeoTIFF raster tile set
crs: API の資産パスは EPSG:4326。実ファイルの CRS は未実読
spatial_coverage: 全球。適用範囲と有効画素は未実読
temporal_coverage: API 版 v2023 のメタデータは 2001-01-01〜2023-12-31
as_of:
  checked: 2026-10-25
contents:
- 樹冠被覆喪失の卓越要因のカテゴリ
- 樹冠被覆率の閾値と喪失年を組み合わせた派生資産
tables:
- name: driver_raster
  read: https://data-api.globalforestwatch.org/dataset/tsc_tree_cover_loss_drivers/v2023
  grain: 卓越する樹冠被覆喪失要因を表すラスタ画素
  rows: null
  id: []
---

# 樹冠被覆喪失の卓越要因

## 出典、規模、API、許諾

- [GFW Data API の目録](https://data-api.globalforestwatch.org/dataset/tsc_tree_cover_loss_drivers)を 2026-10-25 に読み、`is_downloadable=true`、CC BY 4.0、版 `v2023` を確認した。配布元の説明は Curtis らの森林損失要因分類を出典とする。
- [版の資産一覧](https://data-api.globalforestwatch.org/dataset/tsc_tree_cover_loss_drivers/v2023)は 246 件。多くは樹冠被覆率の閾値や喪失年を変えた派生タイルで、246 件の独立した元データではない。ファイル容量と画素数は未確認。
- [fields API](https://data-api.globalforestwatch.org/dataset/tsc_tree_cover_loss_drivers/v2023/fields)で当該レイヤーの `tsc_tree_cover_loss_drivers__driver` を確認した。コードは 1 商品作物などによる森林転換、2 移動耕作、3 林業、4 火災、5 都市化。未分類値は `Unknown` とする。fields 応答には同じ格子の他データセットの列も混ざるため、この列だけを採用する。
- [GFW Data API](https://data-api.globalforestwatch.org/docs)のデータ照会にはキーが必要。匿名で取得できたのはメタデータであり、キー付きの画素取得とリクエスト制限は未検証。

## 利用上の注意

「卓越する要因」は個々の喪失画素の因果効果を証明するものではない。火災、林業、農地転換は複数の要因が重なる。年別の喪失面積と重ねる際は、対象年、樹冠被覆率の閾値、版、集計単位をそろえる。

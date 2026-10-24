---
kind: dataset
id: gfw-forest-carbon-net-flux
description: Global Nature Watchの森林温室効果ガス純フラックス。2001〜2025年の累積値を約30m画素で推定。
url: https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux
license: CC-BY-4.0。再配布可、出典表示が必要
formats:
- Cloud Optimized GeoTIFF
- GeoTIFF tiles
crs: EPSG:4326 (APIの資産パスから。ファイル自体は未実読)
spatial_coverage: 全球の森林
temporal_coverage: 2026-10-25に確認した最新版v20260327は2001〜2025年の累積。年次フラックスではない
as_of:
  checked: 2026-10-25
contents:
- 森林の温室効果ガス純フラックスのモデル推定値
tables:
- name: net_flux_cog
  read: https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux/latest
  grain: 約30m画素。期間全体の累積純フラックス
  rows: null
  id: []
---

# Global Nature Watch 森林炭素純フラックス

## 料金、規模、取得経路

- [GFW Data API のデータセット情報](https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux)を2026-10-25に実際に取得した。`is_downloadable=true`、ライセンスは CC BY 4.0、説明の期間は2001〜2025年。APIの `latest` は `v20260327` を返した。`latest` は将来動くため、再現には版を固定する。
- 同APIの[版の資産一覧](https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux/v20260327)にCOGとラスタタイルがある。画像本体のファイルサイズと認証なし取得の可否は未確認。データの閲覧は無料だが、APIキー、リクエスト制限、ストレージや通信費は利用経路ごとに確認する。[API仕様](https://data-api.globalforestwatch.org/docs)にはAOIによるGeoTIFFのダウンロードと集計がある。
- WRI の旧[紹介ページ](https://datasets.wri.org/datasets/gfw-forest-carbon-net-flux)は2001〜2023年の版を説明しており、記事の2001〜2019年とも違う。分析にはAPIの版を採用し、期間の違う地図を混ぜない。
- 来歴は [Harris らと Gibbs らのモデル](https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux)に基づく純フラックス推定。森林の成長による吸収と攪乱による排出を組み合わせた派生値で、直接観測ではない。

## Hugging Face への凍結

CC BY 4.0 なのでライセンス上は候補。ただしファイル実容量と元データへのアクセス条件が未確認で、数GB級か判断できない。AOI抽出であれば、元版、閾値、期間、単位、元ファイル、処理コード、出典を固定してから検討する。

## 注意

値は年別ではなく25年累積の正味収支。25で割ると期間平均にはなるが、その値を特定年のフラックスに配らない。正味と総排出・総吸収、AGBストックを区別する。

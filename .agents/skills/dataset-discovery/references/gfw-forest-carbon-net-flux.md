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
- 2026-10-26に[v20260327の資産一覧](https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux/v20260327)を再照会し、7つのCOGと8つのラスタタイルを確認。COGは `net_flux_forest_extent_per_hectare_v1_4_3_2001_2025.tif` など。S3オブジェクトへの匿名HEADは403、APIのGeoTIFFダウンロードは有効なAPIキーが無いと403になった。公式[API仕様](https://data-api.globalforestwatch.org/docs)に認証とAPIキー作成手順、AOIダウンロード手段がある。取得にはユーザーのGFW APIキーが必要。
- 最新版とは別に、論文で使われた旧Dataverse版1.3.2 (2001〜2023年) が公開され、Dataverseの個別metadataではCC0 1.0。東北海道切り出しを[別reference](gfw-forest-carbon-net-flux-hokkaido-east-v1-3-2.md) と [Hugging Face](https://huggingface.co/datasets/yuiseki/gfw-forest-carbon-net-flux-hokkaido-east-2001-2023-v1-3-2) に公開した。旧版のライセンスや値を現行API版に適用しない。
- WRI の旧[紹介ページ](https://datasets.wri.org/datasets/gfw-forest-carbon-net-flux)は2001〜2023年の版を説明しており、記事の2001〜2019年とも違う。分析にはAPIの版を採用し、期間の違う地図を混ぜない。
- 来歴は [Harris らと Gibbs らのモデル](https://data-api.globalforestwatch.org/dataset/gfw_forest_carbon_net_flux)に基づく純フラックス推定。森林の成長による吸収と攪乱による排出を組み合わせた派生値で、直接観測ではない。

## Hugging Face への凍結

現行版v20260327はCC BY 4.0なのでライセンス上は候補。版、資産、値の意味は確認済みだが、APIキーが無く、COGの容量とAOIデータ本体は未取得。キーを設定した後に地域と閾値を選び、元版、期間、単位、取得ファイルのチェックサム、処理コード、出典を固定してGeoParquet化する。旧Dataverse v1.3.2の公開版を現行版の代用として扱わない。

## 注意

値は年別ではなく25年累積の正味収支。25で割ると期間平均にはなるが、その値を特定年のフラックスに配らない。正味と総排出・総吸収、AGBストックを区別する。

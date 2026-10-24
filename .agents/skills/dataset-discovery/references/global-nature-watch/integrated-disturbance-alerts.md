---
kind: dataset
id: gfw-integrated-dist-alerts
description: GLAD-L、GLAD-S2、RADD、DIST-ALERT を統合した全球植生攪乱の速報ラスタ。
url: https://data-api.globalforestwatch.org/dataset/gfw_integrated_dist_alerts
license: CC BY 4.0。GFW Data API の個別メタデータに記載。出典表示が必要
formats:
- Cloud Optimized GeoTIFF
- GeoTIFF raster tile set
crs: API の資産パスは EPSG:4326。実ファイルの CRS は未実読
spatial_coverage: 全球。ただし各観測系の適用範囲と有効画素は異なる
temporal_coverage: API 版 v20261024 のメタデータは 2014-12-31〜2026-10-24。説明文は 2019 年以降で直近 2 年を表示とする
as_of:
  checked: 2026-10-25
contents:
- アラート発生日と信頼度
- 攪乱の強度と観測系の重なり
tables:
- name: alerts_raster
  read: https://data-api.globalforestwatch.org/dataset/gfw_integrated_dist_alerts/v20261024
  grain: 植生攪乱の約 10 m 画素の速報値
  rows: null
  id: []
---

# 全球の植生攪乱統合アラート

## 出典、規模、API、許諾

- [GFW Data API のデータセット](https://data-api.globalforestwatch.org/dataset/gfw_integrated_dist_alerts)は `is_downloadable=true`、CC BY 4.0、説明に daily・10 m・global と記載する。GLAD-L、GLAD-S2、RADD、DIST-ALERT の統合結果で、森林だけに限定しない。
- 2026-10-25 に[版 `v20261024`](https://data-api.globalforestwatch.org/dataset/gfw_integrated_dist_alerts/v20261024)の資産 4 件を実読した。うち COG が 2 件、tile set が 2 件。元ファイルの合計バイト数、画素数、NoData と各センサーの寄与率は未確認。資産一覧の件数をアラート件数と取り違えない。
- メタデータの `content_date_range` は 2014-12-31〜2026-10-24、説明は 2019 年以降で直近 2 年の表示とする。食い違いがあるため、期間の分析では値を読む前に日付分布と有効画素を確かめる。
- [GFW Data API 仕様](https://data-api.globalforestwatch.org/docs)では AOI の照会や GeoTIFF 取得を案内する。キーなしの実データ照会は 403 になったため、無料の公開サービスでもアカウントとキーが要る。キー付きでの画素取得は未検証。

## 利用上の注意

これは確定した森林減少面積ではなく、複数の衛星検出を統合した速報。観測可能性、雲、季節、地表型、検出系ごとの分解能でアラートの出方が変わる。アラートが無いことを「攪乱ゼロ」とせず、対象地域のカバレッジを確認する。`latest` ではなく版を固定する。

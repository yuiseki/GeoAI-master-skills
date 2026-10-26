---
kind: catalog
id: global-nature-watch
description: WRI の Global Nature Watch と Land & Carbon Lab が案内する生態系データの入口。データ本体と許諾はレイヤーごとに異なる。
url: https://www.globalnaturewatch.org/
access: GFW Data API の目録は匿名で読める。データ照会は API キーが必要な場合がある。外部配布元の API は各カードを参照
license: 目録全体の一律ライセンスはない。各データセットのメタデータと配布元の条件を確認する
crs: レイヤーごとに異なる
spatial_coverage: 全球を中心とするがレイヤーごとに異なる
temporal_coverage: レイヤーと版ごとに異なる
as_of:
  checked: 2026-10-25
contents:
- 草地の年次分類
- 植生攪乱の統合アラート
- 森林損失の主因
- 森林タイプの2020年基準図
---

# Global Nature Watch のデータ入口

[WRI の発表](https://www.wri.org/news/release-global-forest-watch-becomes-global-nature-watch-expanding-cover-more-land-ecosystems)によると、2026 年 9 月に Global Forest Watch が Global Nature Watch に改称し、森林以外にも対象を広げた。旧 GFW のデータとワークフローは引き続き利用できる。GNW の [Horizon](https://horizon.globalnaturewatch.org/) はデータを探して分析するプレビュー画面であり、それ自体は 1 つの固定データセットではない。

## 目録と認証

- [GFW Data API](https://data-api.globalforestwatch.org/docs) の `GET /datasets` と `GET /dataset/{id}` は、2026-10-25 に認証なしで応答した。`GET /dataset/{id}/{version}` で版と資産一覧を読める。`latest` は固定版ではない。
- 同日、`gpw_grasslands_2024/v1.1/query/json` に小さなポリゴンを送ると 403 `Request is missing valid API key` だった。公開メタデータの取得成功を、匿名で画素を読める証拠にしない。[API キーの案内](https://globalnaturewatch.org/help/developers/guides/create-and-use-an-api-key/)に従い、アカウントとキーを用意する。キーを使った実データ照会は未検証。
- WRI は GNW のデータを無料で提供すると[説明](https://www.wri.org/news/release-global-forest-watch-becomes-global-nature-watch-expanding-cover-more-land-ecosystems)しているが、API のキーやリクエスト制限、外部ホストの通信費は別に確認する。ここでは有料契約を前提にしない。
- [GNW の利用規約](https://globalnaturewatch.org/terms/)は、第三者データに個別のライセンスと制限があると明記している。GFW Data API のメタデータで `license: null` のデータを、他の CC BY 4.0 のデータと同じ許諾として扱わない。
- 旧 GFW の一般向け Data API と [GFW Pro API](https://gfwpro.globalforestwatch.org/) は別物。後者は 2026-12-31 に終了予定なので、ここにある一般向けの API と混同しない。

## 個別カード

- [Global Pasture Watch の年次草地分類](gpw-grasslands.md)
- [全球の植生攪乱統合アラート](integrated-disturbance-alerts.md)
- [森林損失の主因](tree-cover-loss-drivers.md)
- [ForTy 森林タイプ 2020](forest-typology-2020.md)（東北海道6タイルの GeoParquet 派生版を公開）
- [ForTy 2020 の検証標本 GeoParquet](../../references/huggingface/yuiseki/forest-typology-validation-2020.md)

既存の [森林炭素純フラックス](../gfw-forest-carbon-net-flux.md)と[2000年の木本バイオマス](../gfw-biomass-stock-2000.md)は既に別カードにあるため、ここでは重複させない。自然地図 `sbtn_natural_lands` は 2026-10-25 時点で GFW Data API の目録にあるが、版一覧が空で、同 API から取得できる固定版を確認できなかったため追加していない。

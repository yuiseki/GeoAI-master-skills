---
kind: dataset
id: gpw-grasslands
description: Global Pasture Watch の全球草地の年次分類。自然・半自然の草地と管理された草地を区別するモデル推定図。
url: https://data-api.globalforestwatch.org/dataset/gpw_grasslands_2024
license: GFW API の個別メタデータは null。提供元の Zenodo 配布は CC BY 4.0。コードの MIT 許諾とは区別する
formats:
- GFW Data API の raster tile set
- Zenodo の Cloud Optimized GeoTIFF
crs: GFW API の資産パスは EPSG:4326。実ファイルの CRS は未実読
spatial_coverage: 全球の陸域。個別年の有効画素は未実読
temporal_coverage: 配布元の 2000〜2024 年の年次図。GFW API では 2024 年の分類版 v1.1 を確認
as_of:
  checked: 2026-10-25
contents:
- 管理された草地と自然・半自然の草地の分類
- 配布元には年別の分類図とクラス確率がある
tables:
- name: grassland_2024
  read: https://data-api.globalforestwatch.org/dataset/gpw_grasslands_2024/v1.1
  grain: 2024 年の分類ラスタ画素
  rows: null
  id: []
---

# Global Pasture Watch の草地分類

## 出典、規模、API、許諾

- [GFW Data API の目録](https://data-api.globalforestwatch.org/dataset/gpw_grasslands_2024)で `is_downloadable=true` と `v1.1` を 2026-10-25 に確認した。[版の資産一覧](https://data-api.globalforestwatch.org/dataset/gpw_grasslands_2024/v1.1)は EPSG:4326 の raster tile set を 1 件返す。ただし `is_latest=false` なのに目録の版一覧は 1 件だけだったため、`latest` を使わず版を明記する。
- 同 API のデータ照会は、キーを付けない小ポリゴンの `POST /query/json` で 403 となった。メタデータは匿名で取得できるが、画素の API 取得にはキーが必要で、キーを使った成功例は未確認。
- [配布元の Zenodo レコード](https://zenodo.org/records/15648551)は CC BY 4.0 で、2018〜2020 年の分類 COG 3 枚の合計は 48,194,350,199 バイト。2020 年の 1 ファイルは 16,070,137,188 バイト。これは 2024 年版の容量ではない。2024 年のファイルサイズと全期間の合計容量は未確認。Zenodo の公開 API `GET https://zenodo.org/api/records/15648551` は認証なしで応答した。
- [提供元のリポジトリ](https://github.com/wri/global-pasture-watch)は、分類図、確率図、GEE、STAC、Zenodo の複数の配布先を案内する。GFW API 版と Zenodo 版の画素が同一かは未照合。GFW API の `license: null` を Zenodo の許諾で上書きしない。

## 利用上の注意

草地面積は分類モデルの推定で、現地で確認した面積ではない。自然・半自然の草地と管理草地を混ぜると保全上の問いが変わる。年を比較する際は製品の版、クラス定義、境界、NoData をそろえる。実ファイルの画素分布と欠損率は未実測。

Zenodo v2-beta の 2018〜2020 年の dominant-class COG は CC BY 4.0 で再配布できる。2026-10-25、東北海道の範囲読みにより原典各16 GBの COG 全体を取得せず、対象画素のクロップを作成した。GeoParquet は10×10ソース画素ごとのクラス数を含み、クロップ元のMD5、クロップと変換物のSHA-256を残して [Hugging Face](https://huggingface.co/datasets/yuiseki/gpw-grasslands-hokkaido-east-2018-2020-250m) に固定した。年別の範囲・分類値とライセンスは[東北海道の固定版カード](gpw-grasslands-hokkaido-east-2018-2020.md)を参照。これは GFW API の別製品 `gpw_grasslands_2024` とは異なる配布物であり、Zenodo の許諾を GFW API の `license: null` に当てはめない。

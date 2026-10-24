---
kind: dataset
id: ctrees-agb-100m
description: CTrees が推定した全球の地上部バイオマス密度と不確実性の年次100mラスタ。
url: https://registry.opendata.aws/ctrees-agb-100m-global/
license: CC-BY-4.0。再配布可、出典表示が必要
formats:
- Cloud Optimized GeoTIFF
- Icechunk
crs: EPSG:4326 (配布元のカタログ記載。ファイル自体は未実読)
spatial_coverage: 全球の植生のある陸域
temporal_coverage: 2000〜2025年、年次
as_of:
  checked: 2026-10-25
contents:
- 地上部バイオマス密度の推定値 (Mg/ha)
- 推定の不確実性
tables:
- name: annual_cogs
  read: s3://ctrees-agb-100m-global/cogs/
  grain: 年 × 100m画素。AGBと不確実性が別のCOG
  rows: null
  id: []
  columns:
  - name: agb
    type: raster
    meaning: 地上部バイオマス密度のモデル推定値 (Mg/ha)。炭素量ではない
---

# CTrees の全球地上部バイオマス

## 料金、規模、取得経路

- データ取得は無料。Earthmover の無料アカウントから利用できるほか、AWS Open Data の S3 バケットは匿名で一覧とダウンロードができる。AWS、Earthmover、転送先の計算・保存・通信費は別に確認する。
- 2026-10-25 に `aws s3 ls --no-sign-request s3://ctrees-agb-100m-global/cogs/ --recursive --summarize` を実行し、54 オブジェクト、1,903,959,046,855 バイトを確認した。うち年次AGBと不確実性のCOGが26年 × 2ファイルで、2000年のAGBは38,097,412,231バイト、不確実性は35,285,977,829バイト。残りは補助ファイル。ラスタ画素の値は未実読。
- 入口は [AWS Open Data 登録](https://registry.opendata.aws/ctrees-agb-100m-global/) と [CTrees の公開案内](https://ctrees.org/news/2026-aboveground-biomass-data-release)。AWS では `cogs/` にCOG、`agb_100m_global/` にIcechunkがある。専用の検索APIは未確認。COGをHTTP Rangeで部分読みする方法はあるが、実動作は未確認。
- ライセンスは AWS Open Data 登録で [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) と明記。再配布・改変は出典表示等の条件付きで可能。
- 来歴は CTrees のモデル推定値。衛星画像、航空機LiDAR、現地調査・森林インベントリ等を組み合わせると[CTrees](https://ctrees.org/news/2026-aboveground-biomass-data-release)が説明する。独立した地上真値ではない。

## Hugging Face への凍結

全球・全期間の複製は約1.90 TBなので対象外。日本など対象範囲、対象年、AGBと不確実性を選んだ切り出しなら候補。ただし切り出した結果は派生物なので、原本の版、取得日、切り出し範囲、画素変換の有無、各ファイルのハッシュ、CC BY 4.0 の表示を記録する。数GBに収まるかは切り出し後の実測が必要。公開版を作ったわけではない。

## 注意

100m は粒度であり、1画素の実測精度ではない。年ごとの数値を単純に引いて変化と断定せず、不確実性、モデルの版、時間外挿を確認する。ほかの衛星由来の推定値との比較を「独立した現地検証」とは呼ばない。

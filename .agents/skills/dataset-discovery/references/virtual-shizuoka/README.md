---
kind: catalog
id: virtual-shizuoka
description: 静岡県の公開3次元点群 VIRTUAL SHIZUOKA。年・地域ごとの LAS 等を公開 S3 から取得する目録。
url: https://registry.opendata.aws/virtual_shizuoka/
access: s3://virtual-shizuoka を署名なしで一覧・取得できる。必要な年とタイルだけ選ぶ
license: AWS Open Data Registry の表示は CC BY 4.0 と ODbL 1.0。適用範囲・二重表記の意味は元配布元で要確認
crs: 年・タイルごとに確認。実読した LAS は CRS 記録が無く、座標系を特定できなかった
spatial_coverage: 静岡県の公開済み範囲。AWS Registry は7200/7777 km2と説明
temporal_coverage: 公開 S3 に2019、2020、2021、2022、2025の年別プレフィックスを確認
as_of:
  checked: 2026-10-25
contents:
- 航空レーザー測量の3次元点群
- 年・地域・点群区分ごとの ZIP と LAS
---

# VIRTUAL SHIZUOKA

[AWS Open Data Registry](https://registry.opendata.aws/virtual_shizuoka/)の公開バケット `s3://virtual-shizuoka` から必要なタイルだけ選ぶ。2026-10-25 に2025年 `LP/Original/08/MC/49/08MC4928.zip` (309,319バイト) を実読した。中の `08MC4928.las` は599,105バイト、LAS 1.2、point format 3、17,614点。分類コード2、3、6、8があった。

LAS の座標はおよそ X=-40,405〜-40,400、Y=-72,900〜-72,699、Z=2,354〜2,433だったが、LAS の `parse_crs()` は `None`。値から座標系や鉛直基準を推測して他の地図に重ねない。元の測量仕様・図郭の座標参照系を確認してから使う。年の違うタイルが同じ観測時点・同じ品質とは限らない。

Registry のライセンス欄には CC BY 4.0 と ODbL 1.0 がともに表示される。どのファイルにどちらが適用されるか未確認のため、再配布・再ホストは保留する。配布範囲の面積も Registry の公称値であり実測ではない。

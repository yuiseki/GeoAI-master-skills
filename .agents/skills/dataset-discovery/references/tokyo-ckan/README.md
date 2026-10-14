---
kind: catalog
id: tokyo-ckan
description: 東京都と区市町村が CKAN で公開しているデータセットの目録 (施設一覧、統計表など)。yuiseki が作った非公式の STAC で、持っているのはメタデータだけ。
url: https://stac.yuiseki.net/tokyo-ckan/
access: items.parquet と assets.parquet を DuckDB で読む。使い方の正本は目録の AGENTS.md。ファイルは各組織のサイトにある
license: ほぼ CC-BY-4.0。データセットごとに確かめる
crs: 不明 (データごとに違う)
spatial_coverage: 東京都。目録の場所は公開した組織の管轄区域の矩形で、推定値
temporal_coverage: 目録の時刻は推定値。データの時期を表すのは datetime_basis が resource-name か dataset-title のものだけ
as_of:
  checked: 2026-10-10
contents:
- 施設一覧
- 統計表
- 区市町村のオープンデータ
tables:
- name: items
  read: https://stac.yuiseki.net/tokyo-ckan/items.parquet
  grain: 1 つのデータセット
  rows: 9698
  id: []
- name: assets
  read: https://stac.yuiseki.net/tokyo-ckan/assets.parquet
  grain: 1 つのファイル
  rows: 83821
  id: []
---

# 東京都オープンデータカタログ (tokyo-ckan)

東京都と区市町村が CKAN で公開しているデータセットの目録。施設一覧、統計表など。yuiseki が作った非公式の STAC で、持っているのはメタデータだけ。ファイルは各組織のサイトにある。

## 目録の引き方

- 入口: `https://stac.yuiseki.net/tokyo-ckan/`
- 使い方の正本は目録の直下の `AGENTS.md` (`https://stac.yuiseki.net/tokyo-ckan/AGENTS.md`)。表から始めること、区市町村を比べるなら共通項目 (family) から入ること、推定した項目をどこまで信じるかが書いてある。まずそれを読む。
- 1 組織が 1 コレクション、1 データセットが 1 item、1 ファイルが 1 asset。
- `items.parquet` (2026-10-10 に 9,698 行) と `assets.parquet` (83,821 行) が表。`catalog.json` もある。`collections.parquet` は無い (404)。

## 気をつけること

- CKAN には場所も時刻も無いので、目録の場所と時刻は推定値。推定の根拠は `tokyo:footprint_basis` と `tokyo:datetime_basis`。場所は公開した組織の管轄区域の矩形で、データの点がその中にあるとは限らない。
- 時刻がデータの時期を表すのは、`datetime_basis` が `resource-name` か `dataset-title` のものだけ。
- 同じ名前のデータセットでも列の構成が同じとは限らない。`family_layout_match` で確かめる。
- ファイルのリンクは切れる。以前の調査の記録 (未確認)では、23 区の施設一覧の CSV 194 件のうち 11 件が 2026-09-28 に 404 で、残り 183 件を `https://z.yuiseki.net/static/tokyo-ckan-files/` に中身を変えずに置いてある。文字コードは UTF-8、CP932、UTF-16 が混ざり、緯度と経度の列があっても値が空のものが多い。
- ライセンスはほぼ CC-BY-4.0。データセットごとに確かめる。

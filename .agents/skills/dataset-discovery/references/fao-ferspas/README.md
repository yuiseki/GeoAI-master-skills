---
kind: catalog
id: fao-ferspas
description: FAO が公開している農業・食料・気候のラスタ (干ばつ指数、作物の適地、土壌、降水、気温 AgERA5 など) の目録。yuiseki が作った非公式の目録で、持っているのはメタデータだけ。
url: https://stac.yuiseki.net/fao-ferspas/
access: items.parquet を DuckDB で読む。ファイル (COG) は FAO の Google Cloud Storage にあり、gs:// を https://storage.googleapis.com/ に置き換えると匿名で読める (一部のバケットは 403)
license: コレクションごと。collections.parquet の license 列 (AgERA5 の降水・基準蒸発散量と日別気温は主に CC-BY-SA-4.0。月別平均最高・最低気温コレクションは CC-BY-4.0)
crs: コレクションごとに違う
spatial_coverage: 全世界
temporal_coverage: コレクションごと
as_of:
  checked: 2026-10-10
contents:
- 干ばつ指数
- 作物の適地
- 土壌
- 降水
- 気温
tables:
- name: items
  read: https://stac.yuiseki.net/fao-ferspas/items.parquet
  grain: 1 つのファイル
  rows: 639947
  id: []
- name: collections
  read: https://stac.yuiseki.net/fao-ferspas/collections.parquet
  grain: 1 つのコレクション
  rows: 1921
  id: []
---

# FAO の農業・食料系ラスタ (fao-ferspas)

FAO が公開している農業・食料・気候のラスタの目録。干ばつ指数、作物の適地、土壌、降水、気温 (AgERA5) など。yuiseki が作った非公式の目録で、持っているのはメタデータだけ。ファイル (COG) は FAO の Google Cloud Storage にある。

## 目録の引き方

- 入口: `https://stac.yuiseki.net/fao-ferspas/`
- 静的な STAC の JSON は無く、GeoParquet の表が本体。`catalog.json` と `AGENTS.md` は無い (404)。
- `items.parquet` は 1 行が 1 ファイルで、2026-10-10 に 639,947 行。`season`、`crop`、`ssp` などの次元が列になっている。
- `collections.parquet` は 1,921 行。ライセンスは `license` 列。
- 以前の調査の記録 (未確認)では、`search.parquet` が全文検索の索引、`embeddings*.parquet` が意味検索のベクトル (ここでは確かめていない)。

```sql
load httpfs;
select count(*) from 'https://stac.yuiseki.net/fao-ferspas/items.parquet';
```

## ファイルの読み方 (以前の調査の記録、未確認、2026-09-28)

- `data_href` の `storage.cloud.google.com` は Google のログインに飛ばされて取れない。`data_gs_href` の `gs://` を `https://storage.googleapis.com/` に置き換えると匿名で読める。
- 57 のバケットのうち 3 つは匿名だと 403: `fao-gismgr-asis-data` (18,917 ファイル、農業ストレス指数など)、`fao-gismgr-rdms-data` (1,245)、`fao-gismgr-seap-data` (1)。
- 読めるバケットのファイルは COG で、範囲を部分読みできる。AgERA5 の月別は 1 ファイルが 1 か月の全球 (3,600 × 1,800、0.1 度、float32、欠損値 -9999)。日本の範囲の 1 か月を約 4 秒で読めた。
- ライセンスはコレクションごと。2026-10-26 に目録を実照会した結果、AgERA5 の降水と基準蒸発散量、日別の最高・最低気温は CC-BY-SA-4.0、月別平均最高気温 `AGERA5-TMAX-AVG-M` と月別平均最低気温 `AGERA5-TMIN-AVG-M` は CC-BY-4.0。隣のコレクションからライセンスを推測しない。
- 月別平均最高・最低気温の日本周辺GeoParquet切り出しは [別reference](../../references/huggingface/yuiseki/agera5-japan-monthly-temperature-1979-2026.md) と [Hugging Face](https://huggingface.co/datasets/yuiseki/agera5-japan-monthly-temperature-1979-2026) にある。

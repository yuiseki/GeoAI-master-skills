# FAO の農業・食料系ラスタ (fao-ferspas)

FAO が公開している農業・食料・気候のラスタの目録。干ばつ指数、作物の適地、土壌、降水、気温 (AgERA5) など。yuiseki が作った非公式の目録で、持っているのはメタデータだけ。ファイル (COG) は FAO の Google Cloud Storage にある。

## 目録の引き方

- 入口: `https://stac.yuiseki.net/fao-ferspas/`
- 静的な STAC の JSON は無く、GeoParquet の表が本体。`catalog.json` と `AGENTS.md` は無い (404)。
- `items.parquet` は 1 行が 1 ファイルで、2026-10-10 に 639,947 行。`season`、`crop`、`ssp` などの次元が列になっている。
- `collections.parquet` は 1,921 行。ライセンスは `license` 列。
- 以前の調査の記録では、`search.parquet` が全文検索の索引、`embeddings*.parquet` が意味検索のベクトル (ここでは確かめていない)。

```sql
load httpfs;
select count(*) from 'https://stac.yuiseki.net/fao-ferspas/items.parquet';
```

## ファイルの読み方 (以前の調査の記録、2026-09-28)

- `data_href` の `storage.cloud.google.com` は Google のログインに飛ばされて取れない。`data_gs_href` の `gs://` を `https://storage.googleapis.com/` に置き換えると匿名で読める。
- 57 のバケットのうち 3 つは匿名だと 403: `fao-gismgr-asis-data` (18,917 ファイル、農業ストレス指数など)、`fao-gismgr-rdms-data` (1,245)、`fao-gismgr-seap-data` (1)。
- 読めるバケットのファイルは COG で、範囲を部分読みできる。AgERA5 の月別は 1 ファイルが 1 か月の全球 (3,600 × 1,800、0.1 度、float32、欠損値 -9999)。日本の範囲の 1 か月を約 4 秒で読めた。
- ライセンスはコレクションごと。AgERA5 の雨と基準蒸発散量は CC-BY-SA-4.0、気温は CC-BY-4.0。

---
kind: catalog
id: mlit-nlftp
description: 国土交通省の国土数値情報の目録 (鉄道、バス停、医療機関、学校、浸水想定区域、将来推計人口メッシュなど)。yuiseki が作った非公式の STAC で、持っているのはメタデータだけ。
url: https://stac.yuiseki.net/mlit-nlftp/
access: items.parquet を DuckDB で読む。使い方の正本は目録の AGENTS.md。配布は zip だけで、範囲だけを読むことはできない
license: 年とデータセットごとに違う。redistribution 列 (allowed、not-allowed、check) で絞る
crs: JGD2011 と JGD2000 が混ざる
spatial_coverage: 日本。範囲 (footprint) は都道府県の外接矩形
temporal_coverage: 年ごと。is_latest は地域ごとの最新
as_of:
  checked: 2026-10-10
contents:
- 国土数値情報の各データセット
tables:
- name: items
  read: https://stac.yuiseki.net/mlit-nlftp/items.parquet
  grain: 1 つのファイル (データセット × 年 × 地域)
  rows: 21603
  id: []
---

# 国土数値情報 (mlit-nlftp)

国土交通省の国土数値情報の目録。鉄道、バス停、医療機関、学校、浸水想定区域、将来推計人口メッシュなど。yuiseki が作った非公式の STAC で、持っているのはメタデータだけ。ファイル (zip) は国土数値情報の配布元にある。

## 目録の引き方

- 入口: `https://stac.yuiseki.net/mlit-nlftp/`
- 使い方の正本は目録の直下の `AGENTS.md` (`https://stac.yuiseki.net/mlit-nlftp/AGENTS.md`)。入口の選び方、ファイルの選び方、データセットの組み合わせ方、再配布の前に確かめること、目録の弱い所が書いてある。まずそれを読む。
- 横断的な問いには `items.parquet` を 1 回引く。2026-10-10 に 21,603 行 (1 行が 1 ファイル)。`catalog.json` (STAC の木) もある。
- `collections.parquet` と `assets.parquet` は無い (404)。

```sql
load httpfs;
select count(*) from 'https://stac.yuiseki.net/mlit-nlftp/items.parquet';
```

## 気をつけること

- Python の `urllib` の既定の User-Agent では、Cloudflare に 403 を返される。User-Agent を付ければ 200 (2026-10-10 に確かめた)。DuckDB と curl は通る。
- ライセンスはデータセットではなく年に付く。`redistribution` 列 (`allowed`、`not-allowed`、`check`) で絞る。ただし `allowed` でも、国土地理院の承認の注記 (`ksj:source_material`) によってはファイルの再配布に承認が要る (以前の調査の記録、未確認)。分析の結果の公開とファイルの再配布を分けて考える。
- 最新の年は都道府県ごとに違う。`is_latest` は地域ごとの最新。
- 範囲 (footprint) は都道府県の外接矩形で、中身の実測ではない。
- 測地系が JGD2011 と JGD2000 で混ざる。古い Shapefile は Shift-JIS。
- 配布は zip だけで、必要な範囲だけを読むことはできない。東京都の 4 データセットは、GeoParquet にしたミラーが `https://z.yuiseki.net/static/ksj/` にある (以前の調査の記録、未確認)。

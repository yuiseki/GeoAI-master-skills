---
kind: catalog
id: huggingface-yuiseki
description: yuiseki の Hugging Face 公開データのうち、地理分析に使える固定版を探すための目録。
url: https://huggingface.co/yuiseki/datasets
access: 公開リポジトリは匿名で閲覧・ダウンロードできる。個別カードの read は確認した commit SHA に固定する
license: 一律のライセンスはない。各リポジトリの表示と元データの条件を個別カードで区別する
crs: データセットごとに異なる
spatial_coverage: データセットごとに異なる
temporal_coverage: データセットごとに異なる
as_of:
  checked: 2026-10-25
contents:
- yuiseki が Hugging Face に凍結した GeoParquet と原資料・変換コードへの入口
---

# yuiseki の Hugging Face 地理データ

2026-10-25 に[公開一覧](https://huggingface.co/yuiseki/datasets)と Hugging Face Hub API の `GET /api/datasets?author=yuiseki&limit=100&full=true` を照合し、公開79件を確認した。全件が地理データとは限らないため、以下は GeoAI での用途と実ファイルの確認ができた固定版に絞る。先にカード化したデータは[親索引](../../index.md)にも残す。カードの `read` に記した SHA は移動しない版を指す。後続の更新を調べるときは API の `sha` と `siblings` を再確認する。

| カード | 内容 | 元データとの関係 |
|---|---|---|
| [esa-worldcover-tokyo-2021-100m](esa-worldcover-tokyo-2021-100m.md) | 10 m 分類を 100 m セルに集計 | [ESA WorldCover](../../esa-worldcover.md)の派生 |
| [ghsl-japan-core-2020-30arcsec](ghsl-japan-core-2020-30arcsec.md) | 人口・建物面積の 30 秒角セル | GHSL の変換 |
| [forty-hokkaido-east-2020](forty-hokkaido-east-2020.md) | 東北海道の森林タイプ面 | ForTy の地域切り出し |
| [koppen-geiger-east-asia-1991-2020](koppen-geiger-east-asia-1991-2020.md) | 東アジアの気候区分面 | [全球版](../../koppen-geiger-2023.md)とは版・範囲が違う |
| [kontur-population-2023-11-01-22km](kontur-population-2023-11-01-22km.md) | H3 r4 人口推計 | [HDX 版](../../kontur-population-20231101.md)の変換 |
| [microsoft-building-footprints-kanto-2026-08-13](microsoft-building-footprints-kanto-2026-08-13.md) | 関東周辺の建物輪郭 | [元データ](../../microsoft-building-footprints.md)の2タイル |
| [usgs-comcat-2025-m45](usgs-comcat-2025-m45.md) | 2025 年の M4.5 以上の地震 | [更新型 API](../../usgs-earthquake-catalog.md)の抽出 |
| [forest-typology-validation-2020](forest-typology-validation-2020.md) | 森林タイプ検証標本 | 分類図ではなく評価用標本 |
| [timezone-boundary-builder-2026d](timezone-boundary-builder-2026d.md) | 3 種のタイムゾーン境界 | [元データ](../../timezone-boundary-builder.md)の変換 |
| [ibtracs-v04r01](ibtracs-v04r01.md) | 1980 年以降の熱帯低気圧経路 | [NOAA の元データ](../../ibtracs-v04r01.md)の変換 |
| [ctrees-agb-hokkaido-east-100m](ctrees-agb-hokkaido-east-100m.md) | 東北海道の2010年・2025年のAGB集計 | [CTrees 全球版](../../ctrees-agb-100m.md)の切り出し・集計 |
| [gebco-2026-hokkaido-east-15as](gebco-2026-hokkaido-east-15as.md) | 東北海道沖の15秒角標高 | GEBCO 2026 の切り出し。既存の[2025年版](../../gebco-2025.md)とは別 |
| [worldpop-kor-population-2015-2030-1km-r2025a](worldpop-kor-population-2015-2030-1km-r2025a.md) | 韓国の2015〜2030年の年次人口推計 | WorldPop R2025A の変換 |

Hugging Face のカードに表示されたライセンスだけで、元データの再配布条件を確定したとは扱わない。特に `license: other` のカードは元の許諾文を読んでから二次配布する。行数は Parquet のメタデータを読んだ値で、全行の値・形状・一意性を検証したという意味ではない。元の ForTy と GHSL のカードは[親索引](../../index.md)から辿る。

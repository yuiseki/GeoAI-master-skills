---
kind: dataset
id: yuiseki/ibtracs-v04r01
description: NOAA/NCEI が公開配布する IBTrACS v04r01 の since1980 観測点。2026-10-25 の原典 CSV と GeoParquet を固定したスナップショット。
url: https://huggingface.co/datasets/yuiseki/ibtracs-v04r01
card_revision: 7492b1ac35fbbcc304c752d3ff7d381c73a24510
license: IBTrACS Terms of Use。full and open access と open distribution。商用利用は WMO Resolution 40 を指針とし、データセットの引用を求める。CC0 と断定しない
formats:
- GeoParquet 1.1
- 元の CSV
crs: OGC:CRS84。geometry は LON と LAT から作った Point。元の LON が 180 度を超える 7,626 行は geometry で 360 を引き、元列はそのまま残す
spatial_coverage: 全球の熱帯低気圧。観測密度と機関の分布は年代・海域で異なる
temporal_coverage: 1980-01-01〜2026-10-22。最近のデータは後日改訂されることがある
as_of:
  version: v04r01
  subset: since1980
  snapshot: 2026-10-25
  source_last_modified: 2026-10-22T09:01:03Z
  source_bytes: 145156717
  source_sha256: 63e1cd59891af0ded14243466204de4a545adc47476c829f6add3c5be8b57fd6
  hub_revision: 7492b1ac35fbbcc304c752d3ff7d381c73a24510
contents:
- storm ID、UTC 観測時刻、緯度経度、海域、風速、中心気圧、機関別の報告値
- NOAA/NCEI の CSV 原本と、座標ジオメトリ・型を追加した GeoParquet
tables:
- name: since1980
  read: hf://datasets/yuiseki/ibtracs-v04r01@7492b1ac35fbbcc304c752d3ff7d381c73a24510/parquet/since1980/ibtracs.parquet
  grain: 1つの storm の1観測時刻
  rows: 311935
  id:
  - SID
  - ISO_TIME
  join_keys:
  - column: SID
    type: VARCHAR
    meaning: ストーム識別子。位置を同じ storm 内で結ぶ
    unique: false
  - column: ISO_TIME
    type: TIMESTAMP
    meaning: 観測時刻 (UTC)
    unique: false
  no_key:
  - name: uniform_observation_interval
    note: 多くは6時間間隔だが、機関によって3時間や重要時刻の観測を含み、一定間隔ではない
  columns:
  - name: SID
    type: VARCHAR
    meaning: ストーム識別子
  - name: ISO_TIME
    type: TIMESTAMP
    meaning: 観測時刻 (UTC)
  - name: LAT
    type: DOUBLE
    meaning: 緯度 (北緯の度)
  - name: LON
    type: DOUBLE
    meaning: 原典の経度 (東経の度)。180度超の値がある。geometry では -360 度して正規化
  - name: WMO_WIND
    type: DOUBLE
    meaning: WMO 機関の報告風速 (ノット)。機関ごとに平均時間が違い、換算していない
  - name: WMO_PRES
    type: DOUBLE
    meaning: WMO 機関の中心気圧 (mb)
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: LON と LAT から作った点。無効・NULL は無い
---

# IBTrACS v04r01

[NOAA/NCEI の公式ページ](https://www.ncei.noaa.gov/products/international-best-track-archive)が公開する、複数機関の熱帯低気圧ベストトラックを統合したデータ。`yuiseki/ibtracs-v04r01` に since1980 subset の GeoParquet と、取得時の CSV 原本を固定して公開した。NOAA/NCEI は v04r01 を週3回程度更新するため、再現分析では Hub の版と元 CSV の SHA-256 を固定する。

## 公開スナップショット

- Hugging Face: <https://huggingface.co/datasets/yuiseki/ibtracs-v04r01>
- revision: `7492b1ac35fbbcc304c752d3ff7d381c73a24510`
- 原典: `ibtracs.since1980.list.v04r01.csv`。2026-10-25取得、145,156,717 bytes。
- SHA-256: `63e1cd59891af0ded14243466204de4a545adc47476c829f6add3c5be8b57fd6`
- 311,935行、1980-01-01 00:00:00〜2026-10-22 00:00:00 UTC。
- `SID + ISO_TIME` の重複なし。全行のgeometryは有効な Point。
- GeoParquet は `OGC:CRS84`。元の経度は -179.8〜266.9 度で、180度を超える7,626行についてはgeometryを作るときだけ360を引き、CSVと`LON`列は変更していない。
- CSV の2行目は単位で、観測行ではない。元CSVを残しつつ、GeoParquet化ではこの1行を除外した。

DuckDBで読む例:

```sql
install spatial; load spatial;
select SID, ISO_TIME, BASIN, NAME, LAT, LON, WMO_WIND, geometry
from 'hf://datasets/yuiseki/ibtracs-v04r01@7492b1ac35fbbcc304c752d3ff7d381c73a24510/parquet/since1980/ibtracs.parquet';
```

風速は機関ごとに平均時間が異なり、統一されていない。観測間隔も一定ではなく、多くは6時間だが一部機関は3時間や重要時刻の観測を含む。最近の軌跡は provisional のことがあり、後日の再解析で置き換わる。台風の中心位置であり、風域や被害範囲ではない。

## 利用条件と引用

[NOAA/NCEI の Terms of Use](https://www.ncei.noaa.gov/products/international-best-track-archive)は、WDC for Meteorology の full and open access と、地域専門気象センターとの open distribution 合意を説明している。商用利用は WMO Resolution 40 を指針にする。これらの条件をそのまま示し、CC0とは表記していない。公開時には元データの出典と引用を保持する。

NOAA/NCEIは、論文で使う場合にIBTrACSのデータセット論文と版のデータ引用の両方を求めている。詳細は Hugging Face のカードに記載した。

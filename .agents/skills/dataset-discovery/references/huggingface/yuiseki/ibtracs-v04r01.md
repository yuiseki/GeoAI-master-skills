---
kind: dataset
id: yuiseki/ibtracs-v04r01
description: NOAA IBTrACS v04r01 の1980年以降の熱帯低気圧の経路点を GeoParquet に変換した版。
url: https://huggingface.co/datasets/yuiseki/ibtracs-v04r01
license: HF 表示は other、元の NOAA IBTrACS の利用条件へのリンクがある。帰属・再配布条件を元資料で確認する
formats:
- GeoParquet
crs: OGC:CRS84
spatial_coverage: 全球の熱帯低気圧。収録密度と機関の観測品質は時期・海域で異なる
temporal_coverage: 1980年以降、凍結時点までの経路観測。継続更新中の最新観測ではない
as_of:
  checked: 2026-10-25
  hf_revision: 7492b1ac35fbbcc304c752d3ff7d381c73a24510
contents:
- 熱帯低気圧の時刻ごとの経路点と機関別の風速・気圧
tables:
- name: track_points_since1980
  read: https://huggingface.co/datasets/yuiseki/ibtracs-v04r01/resolve/7492b1ac35fbbcc304c752d3ff7d381c73a24510/parquet/since1980/ibtracs.parquet
  grain: 嵐の1時刻の経路観測。1行は1個の嵐ではない
  rows: 311935
  id:
  - SID
  - ISO_TIME
  columns:
  - name: SID
    type: VARCHAR
    meaning: 嵐の識別子
  - name: ISO_TIME
    type: TIMESTAMP
    meaning: 経路点の時刻
  - name: WMO_WIND
    type: DOUBLE
    meaning: WMO の風速。欠測と機関差を確認する
---

# IBTrACS の1980年以降の経路

2026-10-25 に固定版の Parquet メタデータを実読し、311,935行、`SID`・`ISO_TIME`・`LAT`・`LON`・`WMO_WIND` と OGC:CRS84 の点を確認した。`SID` と `ISO_TIME` の組が実際に一意かは未集計で、利用時に検査する。機関別の多数の風速・気圧列が同じ行にあり、列を縦に足して独立した災害件数としない。[NOAA の元データのカード](../../ibtracs-v04r01.md)では last3years CSV を実読しており、こちらは別の1980年以降の凍結版である。

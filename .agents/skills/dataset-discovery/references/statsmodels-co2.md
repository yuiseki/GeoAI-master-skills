---
kind: dataset
id: statsmodels/co2
description: GeoAI の分析対象のデータではなく、時系列の予測の手法を検証するための benchmark (reference dataset)。ハワイのマウナロアで測った大気の CO2 の濃度の週の値 (1958-03〜2001-12)。強い季節 (春に高く秋に低い) と、ほぼ一定の上昇の傾向がある。statsmodels に同梱されていて、ネットワークなしで読める。
url: https://www.statsmodels.org/stable/datasets/generated/co2.html
license: statsmodels の説明では public domain
spatial_coverage: 1 地点 (マウナロア)。座標の列は無い
temporal_coverage: 1958-03-29〜2001-12-29、週ごと
as_of:
  fetched: 2026-10-16
  version: statsmodels 0.15.0 の同梱
contents:
- 週ごとの CO2 の濃度 (ppm)
tables:
- name: co2
  read: statsmodels.api.datasets.co2.load_pandas().data
  grain: 1 週 (土曜日の日付が index)
  id: []
  rows: 2284
  columns:
  - name: co2
    type: DOUBLE
    meaning: CO2 の濃度 (ppm)。59 週が欠ける
---

# マウナロアの CO2 (statsmodels/co2)

statsmodels の説明では、出典は Keeling と Whorf (2004) の、SIO の観測網のフラスコの試料から求めた CO2 の濃度 (CDIAC、2014-03-15 に取得)。季節と傾向の両方を持つ実測の系列として、時系列のモデルの教科書で使われる。

このデータは、GeoAI の分析対象のデータではない。季節のある時系列の予測 (季節ナイーブ、ETS、SARIMA) が、どこで基準に勝つかを確かめるための benchmark として置く。地点は 1 つだけで、空間の問いには答えられない。

## どこから読むか

```python
import statsmodels.api as sm
d = sm.datasets.co2.load_pandas().data  # index は週の日付、列は co2
m = d.co2.resample("MS").mean()          # 月の平均
```

## 中身

2026-10-16 に実測した (statsmodels 0.15.0)。

- 2,284 週、間隔は全て 7 日。59 週が欠ける。
- 月の平均にすると 526 か月で、5 か月が全ての週を欠く: 1958-06、1958-10、1964-02、1964-03、1964-04。
- 最小 313.0 ppm (1958-11-08)、最大 373.9 ppm (2001-05-12)。
- 1965〜2001 年の月の平均を月ごとに並べると、5 月が最も高く (346.5)、9 月と 10 月が最も低い (340.9)。振れ幅は約 5.6 ppm。
- 1965 年の平均から 2001 年の平均までに 50.9 ppm 上がった。

## 気をつけること

- 欠けた月を埋めずに月の系列にすると、1 期間 1 値の前提が崩れる。1965-01 から使えば、欠けた月は無い (444 か月)。
- 季節の周期 12 で使うとき、系列の最初が 1 月になるように切る。
- 2002 年以降の値は入っていない。NOAA が出している今の記録 (別の測定の方法を含む) と値が同じかは確かめていない (未確認)。

## ほかのデータとの結合

結合するキーは無い。1 本の系列として使う。

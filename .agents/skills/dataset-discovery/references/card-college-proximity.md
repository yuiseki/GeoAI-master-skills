---
kind: dataset
id: card/college-proximity
description: GeoAI の分析対象のデータではなく、GeoAI でも使う統計手法 (操作変数) を検証するための benchmark (reference dataset)。Card (1995) の、アメリカの若い男性 3,010 人の教育の年数、1976 年の賃金、1966 年に大学の近くに住んでいたかの印。大学への近さを操作変数にした教育の収益の推定で、教科書の答え (Wooldridge の例 15.4、0.132) が分かっている。
url: https://pypi.org/project/wooldridge/
license: 未確認。Wooldridge の教科書のデータとして、Card が提供したもの (wooldridge パッケージの説明)。このリポジトリには置かず、パッケージから読む
spatial_coverage: アメリカ。位置の列は無く、1966 年と 1976 年の地域 (9 地域、南部、都市圏) の印と、大学の近さの印だけ
temporal_coverage: 1966 年 (住んでいた場所)、1976 年 (教育、賃金)
as_of:
  fetched: 2026-10-16
contents:
- 教育の年数、賃金とその対数、経験、人種、婚姻
- 1966 年に 2 年制と 4 年制の大学の近くに住んでいたかの印 (nearc2、nearc4)
- 1966 年の地域 (reg661〜reg669)、南部、都市圏。1976 年の南部、都市圏
- 両親の教育、IQ、KWW (欠けが多い)
tables:
- name: card
  read: wooldridge.data("card") (pip の wooldridge 0.5.0)
  grain: 若い男性 1 人 (National Longitudinal Survey of Young Men)
  id:
  - id
  rows: 3010
  columns:
  - name: nearc4
    type: BIGINT
    meaning: 1966 年に 4 年制大学の近くに住んでいたら 1 (68.2%)
  - name: educ
    type: BIGINT
    meaning: 1976 年の教育の年数 (平均 13.26)
  - name: lwage
    type: DOUBLE
    meaning: 1976 年の時給 (セント) の対数 (平均 6.262)
---

# 大学への近さ (card-college-proximity)

Card (1995) が、教育の収益を、大学への近さを操作変数にして推定したデータ。National Longitudinal Survey of Young Men の 3,010 人。

このデータは、GeoAI の分析対象のデータではない。操作変数の推定量を検証するための benchmark、reference dataset として置く。地理の情報は、地域と都市圏の印と、大学の近さの印だけ。分析の題材を探すときの候補にはしない。

## どこから読むか

```python
import wooldridge
d = wooldridge.data("card")
```

pip の wooldridge 0.5.0 にデータが入っている (ネットワークは要らない)。

## 中身

2026-10-16 に実測した。

| 項目 | 値 |
|---|---|
| 行 | 3,010 (id で一意) |
| nearc4 が 1 | 68.2% |
| nearc2 が 1 | 44.1% |
| 教育の年数 (nearc4 が 0、1) | 12.70、13.53 |
| 賃金の対数 (nearc4 が 0、1) | 6.155、6.311 |
| 欠け | fatheduc 690、motheduc 353、IQ 949、KWW 47、married 7、libcrd14 13。教科書の例で使う列には欠けが無い |

## 気をつけること

- 教科書の例 15.4 (Wooldridge) の制御変数: exper、expersq、black、smsa、south、smsa66、reg662〜reg669。この組で 2SLS は 0.132 (標準誤差 0.055)、OLS は 0.075。
- 大学の近さは、家庭の豊かさや都市であることとも関わりうる。除外の仮定は、地域と都市圏を制御して置くもので、データからは確かめられない。
- 賃金の単位はセント (時給)。

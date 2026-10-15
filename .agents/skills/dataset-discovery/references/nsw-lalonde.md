---
kind: dataset
id: dehejia/nsw-lalonde
description: National Supported Work Demonstration (NSW) の職業訓練の無作為化実験と、同じ処置群に組み合わせる観察の対照群 (PSID、CPS)。LaLonde (1986) と Dehejia と Wahba (1999、2002) が使った版。実験の答え (処置群と対照群の差) が分かっているので、観察データでの因果の推定量が、その答えに戻るかを試せる。
url: https://users.nber.org/~rdehejia/data/.nswdata2.html
license: 配布元のページに、LaLonde の許可を得てここで公開する、とある。再配布の条件は書かれていない (未確認)。このリポジトリには置かず、配布元から読む
spatial_coverage: アメリカ。実施地や住所の列は無い (地理の情報は入っていない)
temporal_coverage: 1974 年と 1975 年の所得 (処置の前)、1978 年の所得 (結果)
as_of:
  fetched: 2026-10-16
contents:
- 男性の、処置 (職業訓練) の有無、年齢、教育の年数、人種、婚姻、学位の有無、1974、1975、1978 年の所得
- 実験の処置群と対照群 (Dehejia と Wahba の、1974 年の所得のある部分集合)
- 観察の対照群: 家計の調査 PSID と、人口の調査 CPS から取った人
tables:
- name: nsw_dw
  read: https://users.nber.org/~rdehejia/data/nsw_dw.dta
  grain: 実験の参加者 1 人。人を指す ID の列は無い (行の番号だけ)
  id: []
  rows: 445
  columns:
  - name: data_id
    type: VARCHAR
    meaning: 標本の名前。全て Dehejia-Wahba Sample
  - name: treat
    type: FLOAT
    meaning: 1 が処置 (185 人)、0 が実験の対照 (260 人)
  - name: re78
    type: FLOAT
    meaning: 1978 年の所得 (米ドル)。結果
  - name: re74
    type: FLOAT
    meaning: 1974 年の所得。処置群の 70.8%、対照群の 75.0% が 0
- name: psid_controls
  read: https://users.nber.org/~rdehejia/data/psid_controls.dta
  grain: PSID の男性 1 人 (全員 treat = 0)。人を指す ID の列は無い (行の番号だけ)
  id: []
  rows: 2490
- name: cps_controls
  read: https://users.nber.org/~rdehejia/data/cps_controls.dta
  grain: CPS の男性 1 人 (全員 treat = 0)。人を指す ID の列は無い (行の番号だけ)
  id: []
  rows: 15992
---

# NSW の実験と観察の対照群 (nsw-lalonde)

1970 年代のアメリカの職業訓練の無作為化実験 National Supported Work Demonstration の男性の参加者と、同じ処置群に、調査から取った「訓練を受けなかった人」を組み合わせた観察のデータ。LaLonde (1986, American Economic Review) が、観察データの推定が実験の答えを再現できないことを示し、Dehejia と Wahba (1999, JASA、2002, REStat) が傾向スコアで見直した。

地理の列は無い。地理空間のデータではないが、実験の答えが分かっている数少ない公開データなので、因果の推定量の検算に使う。

## どこから読むか

配布元の Stata の形式を、そのまま読む。小さい (合わせて 1 MB に満たない)。

```python
import pandas as pd
d = pd.read_stata("https://users.nber.org/~rdehejia/data/nsw_dw.dta")
```

- 配布元: <https://users.nber.org/~rdehejia/data/.nswdata2.html>
- テキストの形式もある。列の並びは配布元のページにある。
- PSID と CPS には、条件で絞った小さな版 (PSID2 253 人、PSID3 128 人、CPS2 2,369 人、CPS3 429 人) もある。

## 中身

2026-10-16 に実測した (pandas、Stata の形式)。欠損は無い。

| 表 | 行 | 年齢の平均 | 教育の年数 | 黒人の割合 | 既婚の割合 | 1974 年の所得の平均 | 1974 年の所得が 0 | 1978 年の所得の平均 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nsw_dw 処置 | 185 | 25.8 | 10.3 | 0.843 | 0.189 | 2,096 | 0.708 | 6,349 |
| nsw_dw 対照 | 260 | 25.1 | 10.1 | 0.827 | 0.154 | 2,107 | 0.750 | 4,555 |
| psid_controls | 2,490 | 34.9 | 12.1 | 0.251 | 0.866 | 19,429 | 0.086 | 21,554 |
| cps_controls | 15,992 | 33.2 | 12.0 | 0.074 | 0.712 | 14,017 | 0.120 | 14,847 |

## 気をつけること

- 実験の答えは、`nsw_dw` の処置群と対照群の 1978 年の所得の差 1,794.3 ドル。処置群での効果 (ATT) にあたる。観察の対照群と組み合わせたときの比べる先はこの値。
- 観察の対照群は、処置群とまるで違う人たち。PSID の対照は、1974 年の所得の平均が処置群の 9 倍ある。そのまま比べると、差は -15,205 ドル (PSID)、-8,498 ドル (CPS) になる。
- 観察の対照群との組では、処置群に似た対照がわずかしかいない。全体の効果 (ATE) を求めても、処置群に似ていない大多数の対照についての答えをデータは持たない。推定の対象は処置群での効果にする。
- 列は全て float32 で読まれる。`data_id` は文字列なので、数値に変換する前に落とす。
- 所得の単位 (どの年のドルか) は、配布元のページで確かめていない (未確認)。

## ほかのデータとの結合

結合するキーは無い。同じ処置群を、別の対照群の表と縦に積んで使う (`treat == 1` の行を `nsw_dw` から取り、対照の表を足す)。

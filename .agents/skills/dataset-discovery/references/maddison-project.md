---
kind: dataset
id: yuiseki/maddison-project
description: Maddison Project Database の、国ごとの 1 人あたり実質 GDP と人口の長期の推計 (西暦 1 年から 2022 年)。2018、2020、2023 年の 3 つの版を、それぞれ配布のとおりに持つ。
url: https://huggingface.co/datasets/yuiseki/maddison-project
card_revision: d424892d83ebc97431db4d3a43e95c71af2ae4bb
license: CC BY 4.0。図にするときと、12 か国未満で分析するときは、版の Sources の元の論文も引用する
formats:
- Parquet
- xlsx
- dta
crs: null
spatial_coverage: 169 の国と、旧国 (CSK、SUN、YUG)。2018 年版は地域の集計もある
temporal_coverage: 西暦 1 年から 2022 年 (2023 年版)。年が飛ぶ。国がそろうのは 1950 年以降
as_of:
  latest_release: 2023
  fetched: 2026-10-05
contents:
- 1 人あたり実質 GDP (2011 年の米ドル)
- 年央の人口 (千人)
- 2018 年版の地域の集計と、1990 年の米ドルの系列
tables:
- name: full_data_2023
  read: hf://datasets/yuiseki/maddison-project/parquet/2023/full_data.parquet
  grain: 国 × 年。どの国かに値がある年は全ての国に行があり、ほとんどの行は空
  rows: 131144
  id:
  - countrycode
  - year
  join_keys:
  - column: countrycode
    type: VARCHAR
    meaning: ISO の 3 文字の国コード。旧国 CSK、SUN、YUG を含む
    joins:
    - worldbank-wdi:countries.Country Code (CSK、SUN、TWN、YUG は WDI に無い)
  columns:
  - name: gdppc
    type: DOUBLE
    meaning: 1 人あたり実質 GDP (2011 年の米ドル)。21,366 行に値がある
  - name: pop
    type: DOUBLE
    meaning: 年央の人口 (千人)。17,875 行に値がある
  - name: region
    type: VARCHAR
    meaning: 2023 年版の 8 つの地域 (East Asia、Sub Saharan Africa など)
- name: full_data_2020
  read: hf://datasets/yuiseki/maddison-project/parquet/2020/full_data.parquet
  grain: 国 × 年。値のある行だけ
  rows: 21682
  id:
  - countrycode
  - year
---

# Maddison Project Database (maddison-project)

国ごとの 1 人あたり実質 GDP と人口の、西暦 1 年から現在までの長期の推計。フローニンゲン大学の GGDC が、Angus Maddison の仕事を引き継いで出している。2018、2020、2023 年の 3 つの版があり、版ごとに方法を改めた別の推計。

## どこから読むか

Hugging Face の `yuiseki/maddison-project`。全部で 1 MB に満たない。

```
hf://datasets/yuiseki/maddison-project/parquet/2023/full_data.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/maddison-project>
- 配布元: <https://www.rug.nl/ggdc/historicaldevelopment/maddison/>
- 2018 年版は、2 つの GDP の系列 (`cgdppc` と `rgdpnapc`)、地域の集計 (`2018/regional_data.parquet`)、1990 年の米ドルの系列 (`2018/benchmark_1990.parquet`) も持つ。

## 中身

2023 年版で 2026-10-14 に実測した (DuckDB 1.5.6)。

| 項目 | 値 |
|---|---|
| 行数 | 131,144 (国と年の組は一意)。国 169、年は 1 から 2022 |
| 値のある行 | `gdppc` 21,366、`pop` 17,875 |
| `gdppc` のある国の数 | 1820 年 55、1950 年 146、1990 年 169、2022 年 169 |
| 地域 | 8 つ。Sub Saharan Africa 46、Eastern Europe 32、Latin America 26、Middle East and North Africa 20、Western Europe 19、South and South East Asia 16、East Asia 6、Western Offshoots 4 |
| ライセンス | CC BY 4.0 |

## 気をつけること

- 版を混ぜない。2020 年版と 2023 年版の両方に `gdppc` のある 19,213 の国と年のうち、6,601 で値が違う。系列をつなぐなら 1 つの版だけを使い、版を書く。2018 年版は列の名前も違う (`cgdppc` と `rgdpnapc`)。
- 人口は千人単位。日本の 2018 年は 126,367.71 (千人)。WDI の総人口 (`SP.POP.TOTL`) は 126,811,000 人で、単位をそろえても 0.35% 違う。別の推計なので、どちらかに決める。
- 2023 年版は、どの国かに値がある年の全てに、全ての国の行がある。行の数を国の数や年の数と思わない。値のある行だけで数える。
- 1950 年より前は、国がそろわない (1820 年に 55 か国)。長期の比較は、値のある国が年で入れ替わることを確かめてから行う。国の平均や中央値の時系列は、国の顔ぶれの変化を拾う。
- 旧国 (CSK はチェコスロバキア、SUN はソ連、YUG はユーゴスラビア) が、後継の国と重なる年がある。重ならないかは確かめていない (未確認)。
- 図にするとき、12 か国未満で分析するときは、版の Sources の元の論文を引用する (配布元の求め)。

## ほかのデータとの結合

- 国の属性や他の指標: `countrycode` が `worldbank-wdi` の `countries.Country Code` と同じ ISO の 3 文字。2026-10-14 に、2023 年版の 169 のうち、CSK、SUN、TWN、YUG の 4 つが WDI の国の表に無かった。台湾 (TWN) は WDI に無い。
- 国の面: `natural-earth` の国の面と結ぶときは、Natural Earth の ISO のコードの欠け (-99) に気をつける (`natural-earth.md`)。

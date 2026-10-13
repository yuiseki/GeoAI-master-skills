---
kind: dataset
id: yuiseki/worldbank-wdi
description: 世界銀行の世界開発指標。国と年ごとの人口、GDP、保健、教育、環境など約 1,400 指標。座標は無い。
url: https://huggingface.co/datasets/yuiseki/worldbank-wdi
license: CC BY 4.0 に世界銀行の紛争解決条項 (調停と仲裁) が加わる。指標ごとに出典の表示が要る。ライセンスが CC BY でない 74 指標は除いてある
formats:
- Parquet
crs: null
spatial_coverage: 国と集計単位 264 (国 217、集計単位 47)。座標なし
temporal_coverage: 1960 から 2025 年。版ごとに別のディレクトリ (最新は 2026-10-01)
as_of:
  release: 2026-10-01
contents:
- 国 × 年 × 指標の値
- 国の表
- 指標の定義
- 注記
tables:
- name: data
  read: hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/data.parquet
  grain: 1 つの値 (国または集計単位 × 指標 × 年)。空の値は行にならない
  rows: 8790085
  id:
  - country_code
  - indicator_code
  - year
  join_keys:
  - column: country_code
    type: VARCHAR
    meaning: 3 文字の国コード。集計単位 (World、地域、所得階層) も入る
    joins:
    - countries.Country Code
    - natural-earth:ne_10m_admin_0_countries.ISO_A3_EH
    note: 国だけにするには countries の Region が空でないものに絞る。215 件が一致する
  - column: indicator_code
    type: VARCHAR
    meaning: 指標のコード (SP.POP.TOTL など)
    joins:
    - series.Series Code
  columns:
  - name: value
    type: DOUBLE
    meaning: 指標の値。単位は指標ごとに series の定義にある。欠損は行が無いことで表す
    missing: 欠損は行が無いこと。NULL の行は 0 行 (実測)
  - name: year
    type: SMALLINT
    meaning: 年 (1960 から 2025)
- name: series
  read: hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/series.parquet
  grain: 1 つの指標 (定義、出典、ライセンスの種類)
  rows: 1441
  id:
  - Series Code
- name: countries
  read: hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/countries.parquet
  grain: 1 つの国または集計単位
  rows: 264
  id:
  - Country Code
  columns:
  - name: Region
    type: VARCHAR
    meaning: 地域。空なら集計単位であって国ではない
---

# World Development Indicators (WDI)

世界銀行の開発指標。国と年ごとの人口、GDP、保健、教育、環境など約 1,400 指標。
分析では、国を単位にした目的変数や説明変数、Natural Earth の国の面に付ける属性に使う。座標は無い。

## どこから読むか

Hugging Face の `yuiseki/worldbank-wdi`。世界銀行が公開した版ごとにディレクトリが分かれている。

```
hf://datasets/yuiseki/worldbank-wdi/parquet/<release>/<table>.parquet
```

- `<release>` は版の日付。2026-10-10 時点で最新は `2026-10-01`。ほかに `2026-07-15`、`2026-04-09`、`2026-02-25`、`2025-12-19`、`2025-07-02`、`2024-05-30`。
- 使った版を必ず報告に書く。版の間で過去の値も改訂される。
- カード: <https://huggingface.co/datasets/yuiseki/worldbank-wdi>

| テーブル | 1 行 |
|---|---|
| `data` | 1 つの値。`country_code`、`indicator_code`、`year`、`value` の縦持ち |
| `countries` | 1 つの国や集計単位。`Region`、`Income Group` などを持つ |
| `series` | 1 つの指標。定義、出典、`License Type` |
| `footnotes`、`country_series`、`series_time` | 値、国と指標、指標と年への注記 |

```sql
select country_code, year, value
from 'hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/data.parquet'
where indicator_code = 'SP.POP.TOTL' and year = 2020;
```

## 粒度と範囲

| 項目 | 値 (版 2026-10-01) |
|---|---|
| 単位 | 国 × 年 × 指標 |
| 値の数 | 8,790,085 (空の値は行にならない) |
| 指標 | 1,441 |
| 国と集計単位 | 264 (うち国は 217、集計単位は 47) |
| 年 | 1960〜2025 |
| ライセンス | CC BY 4.0 に世界銀行の紛争解決条項 (調停と仲裁) が加わる。指標ごとに出典の表示が要る |

## Natural Earth との結合

`countries` で `Region` が空でない 217 件が国。`country_code` を Natural Earth の `ISO_A3_EH` と結ぶ (`ISO_A3_EH` は一意でないので、natural-earth.md の方法で本体の国の行だけにしてから)と 215 件が一致する (2026-10-10 実測)。

一致しない 2 件:

| `country_code` | 名前 | Natural Earth 側 |
|---|---|---|
| `CHI` | Channel Islands | Jersey (`JEY`) と Guernsey (`GGY`) に分かれている |
| `XKX` | Kosovo | `ISO_A3_EH` は `-99`、`ADM0_A3` は `KOS` |

`ADM0_A3` と結ぶと 213 件しか一致しない。WDI には `ISO_A3_EH` のほうが合う。

## 気をつけること

集計単位が混ざっている。 `data` には World、地域、所得階層の値も入っている。国だけにするには `countries` の `Region` が空でないものに絞る。絞らないと、国の平均や回帰に World が 1 行として入る。

```sql
where country_code in (select "Country Code" from countries where "Region" <> '')
```

欠損は行が無いことで表される。 `value` が NULL の行は無い。国 × 年の格子に広げて初めて欠損が見える。指標ごとに年と国の埋まり方が大きく違うので、指標を選んだら国 × 年でいくつ埋まっているかを数える。

欠ける国は無作為ではない。 版 2026-10-01 の 2022 年で、1 人あたり GDP (`NY.GDP.PCAP.CD`) が無い国は 217 か国中 8 か国: イエメン、北朝鮮、キューバ、南スーダン、エリトリアと、英領ヴァージン諸島、ジブラルタル、サン・マルタン。平均寿命 (`SP.DYN.LE00.IN`) は 217 か国すべてにある。紛争中か閉鎖的な国と小さな領土が落ちるので、欠損した行を除くと、紛争と貧困についての結論が偏りうる。

版で系列の形が変わることがある。 中央アフリカ共和国 (`CAF`) の平均寿命 (`SP.DYN.LE00.IN`) は、版 2024-05-30 では 2016〜2022 年が 53.5〜55.0 歳と滑らかだが、版 2025-07-02 以降は 2017 年 45.2、2019 年 31.5、2021 年 40.3、2022 年 18.8 と年ごとに大きく上下し、2009 年は 14.7 (2026-10-10 実測)。この指標の出典は `series` の `Source` によれば国連の World Population Prospects などで、推計の改訂によるものと推測しているが、原因は確かめていない。国の表で他の国から極端に外れるので、クラスタリングでは 1 か国だけの群になった。平均寿命を使うなら、版を書き、極端な値の国を数える。 UCDP GED 26.1 の中央アフリカ共和国の紛争の死者数 (`best` の年合計) と突き合わせると、平均寿命が 40.3 歳に下がる 2014 年は死者が最も多い 2013〜14 年 (約 3,400 人/年) と重なるが、14.7 歳の 2009 年は 244 人、31.5 歳の 2019 年は 507 人、18.8 歳の 2022 年は 773 人で、対応する変化が無い。

この 1 か国が結果を動かす大きさ。 このリポジトリの各スキルの実例 (2022 年の 207 か国の平均寿命) は中央アフリカ共和国を含んだまま書いてある。除いた 206 か国で測り直すと (2026-10-10):

| | 含む | 除く |
|---|---:|---:|
| 線形の R2 (行を無作為に 5 分割) | 0.627 | 0.703 |
| 線形の R2 (地域で分ける) | 0.524 | 0.608 |
| hgb の R2 (行を無作為に) | 0.576 | 0.651 |
| hgb の R2 (地域で分ける) | 0.361 | 0.429 |
| 平均寿命の Moran's I (6 近傍) | 0.595 | 0.669 |
| 線形の残差の Moran's I | 0.264 | 0.357 |

線形が hgb に勝つこと、地域で分けるほうが厳しいこと、残差に自己相関が残ることは変わらない。点数の大きさは 1 か国で 0.07〜0.08 動く。

除いた指標がある。 ライセンスが CC BY でない 74 指標は全版から除かれている。SIPRI の軍事費、Climate Watch の CO2 排出 (`EN.ATM.CO2E.*`)、IEA のエネルギーなど。一覧は各版の `excluded.json`。欲しい指標が見つからないときはまずここを見る。

版 2026-02-25 は丸められている。 この版だけ有効数字が 11 桁まで。版を比べるときに差が出るが、改訂ではない。

列名に空白がある。 `countries` などの注記テーブルは CSV の見出しそのままなので、`"Country Code"` のように二重引用符で書く。

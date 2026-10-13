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

`countries` で `Region` が空でない 217 件が国。`country_code` を Natural Earth の `ISO_A3_EH` と結ぶと 215 件が一致する (2026-10-10 実測)。

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

除いた指標がある。 ライセンスが CC BY でない 74 指標は全版から除かれている。SIPRI の軍事費、Climate Watch の CO2 排出 (`EN.ATM.CO2E.*`)、IEA のエネルギーなど。一覧は各版の `excluded.json`。欲しい指標が見つからないときはまずここを見る。

版 2026-02-25 は丸められている。 この版だけ有効数字が 11 桁まで。版を比べるときに差が出るが、改訂ではない。

列名に空白がある。 `countries` などの注記テーブルは CSV の見出しそのままなので、`"Country Code"` のように二重引用符で書く。

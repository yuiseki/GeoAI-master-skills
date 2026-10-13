---
kind: dataset
id: yuiseki/ucdp-ged
description: Uppsala Conflict Data Program が記録した、1989 年以降の組織的暴力の事件。1 件ごとの場所、日付、当事者、死者数。
url: https://huggingface.co/datasets/yuiseki/ucdp-ged
license: CC BY 4.0。UCDP が版ごとに挙げる論文の引用が条件
formats:
- Parquet
crs: OGC:CRS84
spatial_coverage: 全世界の 126 か国。位置の精度は where_prec で事件ごとに違う
temporal_coverage: 1989-01-01 から 2025-12-31 (版 26.1)。版ごとに過去の事件も改訂される
as_of:
  version: '26.1'
contents:
- 事件の点
- 当事者
- 死者数
- 位置の精度
tables:
- name: ged
  read: hf://datasets/yuiseki/ucdp-ged/parquet/26.1/ged.parquet
  grain: 1 件の事件 (点と期間)
  rows: 417968
  id:
  - id
  join_keys:
  - column: priogrid_gid
    type: BIGINT
    meaning: PRIO-GRID の 0.5 度格子の番号。事件のある格子 8
    003 個だけが行に現れる: null
    unique: false
    joins: []
  - column: country_id
    type: BIGINT
    meaning: Gleditsch and Ward の国の番号
    joins: []
  no_key:
  - name: iso_a3
    note: ISO の国コードは持たない。country は旧名を括弧で添えた UCDP の表記なので、国には点を面に入れて割り当てる
  columns:
  - name: best
    type: BIGINT
    meaning: 死者数の最良の推定。4 つの deaths_* の合計
  - name: where_prec
    type: BIGINT
    meaning: 位置の精度 (1 が正確、3 以上は行政区などの代表点、6 は国まで、7 は公海)
  - name: type_of_violence
    type: BIGINT
    meaning: 1 が国家が当事者の紛争、2 が国家以外の紛争、3 が一方的な暴力
  - name: date_start
    type: TIMESTAMP
    meaning: 事件の開始日
  - name: geometry
    type: geometry:OGC:CRS84
    meaning: 点 (OGC:CRS84)
---

# UCDP Georeferenced Event Dataset (GED)

Uppsala Conflict Data Program が記録した、1989 年以降の組織的暴力の事件。1 件 1 行で、場所、日付、当事者、死者数を持つ。
分析では、時空間の点過程、国や格子への集計、クラスタリング、異常検知、時系列の目的変数に使う。

## どこから読むか

Hugging Face の `yuiseki/ucdp-ged`。UCDP の年 1 回の版ごとにディレクトリが分かれている。

```
hf://datasets/yuiseki/ucdp-ged/parquet/<version>/ged.parquet
```

- `<version>` は `26.1` (最新、2025 年末まで) から `19.1` まで。使った版を必ず報告に書く。
- 版の間で過去の事件も改訂される。同じ年でも版が違えば件数と死者数が違う。
- 各版のコードブック (PDF) が `raw/<version>/ged<version>.pdf` にある。列の意味はそこが正本。
- カード: <https://huggingface.co/datasets/yuiseki/ucdp-ged>

```sql
select year, type_of_violence, sum(best) as deaths
from 'hf://datasets/yuiseki/ucdp-ged/parquet/26.1/ged.parquet'
group by all order by all;
```

## 粒度と範囲

| 項目 | 値 (版 26.1) |
|---|---|
| 単位 | 1 件の事件 (点と期間) |
| 件数 | 417,968 |
| 期間 | `date_start` で 1989-01-01〜2025-12-31 |
| 国 | 126 |
| CRS | `geometry` の CRS 名は `OGC:CRS84` (経度、緯度) |
| ライセンス | CC BY 4.0。UCDP が版ごとに挙げる論文の引用が条件 |

暴力の種類は `type_of_violence` で、1 が国家が当事者の紛争、2 が国家以外の紛争、3 が一方的な暴力。

## 位置の精度

`where_prec` は座標が実際の場所をどれだけ表すか。コードブック 26.1 の定義と、版 26.1 の件数 (2026-10-10 実測)。

| `where_prec` | 意味 | 件数 | 正しく入る単位 |
|---:|---|---:|---|
| 1 | 正確な場所 | 194,544 | 0.5 度格子、第 1 階層の行政区、国 |
| 2 | 既知の点から 25km 以内 | 101,236 | 0.5 度格子 (境界近くは隣の格子のおそれ)、第 1 階層の行政区、国 |
| 3 | 第 2 階層の行政区までしか分からない。その代表点 (多くは重心) | 59,437 | 第 1 階層の行政区、国 |
| 4 | 第 1 階層の行政区までしか分からない。その代表点 | 38,531 | 第 1 階層の行政区、国 |
| 5 | 川、国境、道路などの線か、境界の曖昧な範囲。その代表点 | 18,645 | 国 (範囲が国をまたがなければ) |
| 6 | 国までしか分からない | 5,309 | 国 |
| 7 | 公海か国際空域 | 266 | どの国にも入らない |

3 以上の 122,188 件 (29%) は、座標が事件の場所ではなく行政区などの代表点。点の密度、最近傍距離、空間クラスタリングに使うと、行政区の重心に偽の集積ができる。細かい空間分析では `where_prec` で絞り、絞ったことと除いた件数を書く。

## 格子

`priogrid_gid` は PRIO-GRID の 0.5 度格子の番号。コードブックに格子の大きさは書いていないが、`floor((latitude + 90) / 0.5) * 720 + floor((longitude + 180) / 0.5) + 1` と 26.1 の 417,968 件中 417,920 件で一致する (2026-10-10 実測)。事件のある格子は 8,003 個。事件の無い格子は行として存在しない。

コードブックの注意: 点は、その点を含む格子に付けてある。格子が多数決で割り当てられている国と、点の国が違うことがある。格子の共変量を使うときは、事件ごとに国が合っているかを確かめる。

## Natural Earth との結合

CRS の名前が違うので、そのままでは空間結合できない。 Natural Earth は `EPSG:4326`、こちらは `OGC:CRS84`。DuckDB 1.5 は `ST_Intersects` を拒む。どちらも経度、緯度の順なので `ST_SetCRS(geometry, 'EPSG:4326')` で名前を揃える。

点を Natural Earth の 10m の国の面に入れると、417,968 件のうち 415,081 件がどれかの国に入った (2026-10-10 実測)。2,887 件はどの面にも入らない。

国名で結ぶのは難しい。 `country` は UCDP の表記で、`DR Congo (Zaire)`、`Myanmar (Burma)`、`Russia (Soviet Union)`、`Yemen (North Yemen)`、`Serbia (Yugoslavia)` のように旧名を括弧で添える。Natural Earth の `NAME` か `ADMIN` と一致する事件は 358,543 件。`country_id` は Gleditsch and Ward の番号で、ISO コードではない。国に集計するなら、点を面に入れて決めるほうが確実。ただし `where_prec` が 6 の点は国の代表点なので、面に入れた結果と `country` を照合する。

## 気をつけること

死者数の幅が順序どおりでない。 `best` は 4 つの `deaths_*` の合計。`low` と `high` は下限と上限の推定だが、26.1 では 5,075 件で `low <= best <= high` が成り立たない。区間として使う前に確かめる。

19.1 は別物に近い。 シリアが入っていない。列も 42 列で、20.1 以降の 49 列より少ない。

出典の見出しの列がある。 `source_*` は報道の媒体、日付、見出し。26.1 で 97,496 件が空。

---
name: spatial-data-integration
description: 複数の地理データを、分析の単位として決めた単位に結合する。点を面に入れる、最近傍に割り当てる、キーで結ぶ、単位ごとに集計する。結合の前後で全ての行を数え、落ちた行と重複した行を報告する。
---

# spatial-data-integration

結合は、黙って行を落とし、黙って行を増やす。どの結合でも、入力の全ての行がどうなったかを数えてから先に進む。

## 手順

1. 結合する 2 つのデータについて、CRS の名前、座標の順、結合キーを確かめる。データセットの説明 (CRS、座標の順、結合キーの一致) と、このスキルの [references/duckdb-spatial.md](references/duckdb-spatial.md) を読む。
2. 結合の種類を選ぶ (下の表)。
3. 結合する。入力の各行を、ちょうど 1 つに入った、複数に入った、どれにも入らなかった、に分けて数える。
4. どれにも入らなかった行を見る。種類、場所、値で偏っていないか。最寄りに割り当てるなら距離の上限を決め、割り当てた距離の分布を書く。
5. 複数に入った行の扱いを決める (境界上の点、重なる面)。
6. 単位ごとに集計する。単位の表から左結合して、件数 0 の単位も行として残す。
7. 別の手がかりがあれば照合する。点の属性の国コードと、面に入れて決まった国が一致するか、など。

## 結合の種類

| 種類 | 使う場面 | DuckDB | 気をつけること |
|---|---|---|---|
| 包含 (点を面に) | 点を国、行政区、格子に入れる | `ST_Intersects(面, 点)` | 境界上の点は 2 つの面に入る。海岸の点は面から外れる |
| 最近傍 | 面から外れた点、施設から最寄りの点 | `ST_DWithin` で候補を絞り、距離の最小 | 距離はメートルで測る。上限を決める |
| キー | 国コード、ID で結ぶ | 普通の `join` | 一致しない値を全部書き出す。欠損の符号 (`-99`) |
| 集計 | 単位ごとに件数、合計 | `group by` の後、単位の表から `left join` | 0 の単位を落とさない |

## 点を面に割り当てる

`scripts/assign_points.py` は、点を含む面に割り当て、どの面にも入らなければ上限距離以内の最寄りの面に割り当てる。全ての点を `contained`、`contained_multiple`、`nearest`、`unassigned` のどれかに数え、合計が入力と合わなければ止まる。

```sh
uvx --from 'duckdb>=1.5.5' python scripts/assign_points.py \
  hf://datasets/yuiseki/ourairports-2026-08/parquet/airports.parquet id \
  hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet ADM0_A3 \
  --max-km 5 --out airports_country.parquet
```

テストは `uvx --from 'duckdb>=1.5.5' --with pytest pytest scripts/test_assign_points.py`。

上の例は約 1 分で終わる。結合して分かったデータセット固有のことは、このスキルでなく、そのデータセットの説明 (リポジトリにデータセットごとの reference があればそこ) に書く。

## 書き出すもの

- 結合したデータ、結合の種類、キーか空間の条件
- 入力の行数と、区分ごとの件数
- 最寄りに割り当てた距離の上限と、距離の分布
- 割り当たらなかった行の内訳と、それを除いたことで結論が偏りうる向き
- 別の手がかりとの照合の結果

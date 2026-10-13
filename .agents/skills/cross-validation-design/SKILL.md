---
name: cross-validation-design
description: モデルを何に使うかと、データの依存の構造 (同じ単位の繰り返し、空間の近さ、地域、時間) から分け方を選び、分割表を 1 つ作る。基準もモデルもその分割表で採点する。特徴量ができた後、基準を出す前に使う。
---

# cross-validation-design

評価の分け方は、モデルを本番で何に使うかを真似る。本番で学習データに無いものを予測するなら、評価でもそれを学習から外す。外し方が足りないと、評価は実力より良く見える。

分割は 1 回だけ作り、ファイル (分割表) に残す。eda-and-baseline の基準も spatial-data-modeling のモデルも、同じ分割表で採点する。

## 手順

1. モデルを何に使うかを 1 行で書く。「観測済みの国の来年の値を予測する」「データの無い国の値を埋める」「別の大陸に当てはめる」。
2. データの依存の構造を書き出す。
   - 同じ単位 (国、地点) が何度も出てくるか (パネル)
   - 近い単位どうしが似ているか (空間の近さ)
   - 地域ごとに水準が違うか
   - 時間の順があるか
3. 下の表から分け方を選ぶ。迷ったら、厳しいほうと甘いほうの両方を作る。
4. `scripts/make_folds.py` で分割表を作る。欠損のある行を先に除いた表から作る。
5. 基準とモデルを、その分割表で採点する (`../spatial-data-modeling/scripts/compare_models.py --folds-file`)。
6. 分け方を変えて点数を比べる。甘い分け方と厳しい分け方の差が大きいなら、甘い分け方は依存の構造でリークしている。どのモデルがどれだけ落ちるかも見る。
   比べるときは、採点した行を揃える。時間の分割は最初の時点の行を試験しないので、`compare_models.py` の `n` が分け方で違う。行の違う点数を並べると、分け方の違いと行の違いが混ざる (study-geoai-algo-py の 001 では、はじめ 2,246 行と 1,917 行の点数を並べていて、揃え直した)。揃えるなら、全ての分け方で試験される行だけの表を作り、その表から分割表を作り直す。
   点数の揺れは、行の数ではなく独立な単位の数で考える。同じ月の格子どうし、同じ国の年どうしは独立でない。study-geoai-algo-py の 006 では、試験の 39,720 行 (格子 × 月) のうち独立に近いのは 120 か月だった (uncertainty-estimation の references/intervals.md)。
7. 書き出す。

## 使い道と分け方

| モデルの使い道 | 分け方 | reference |
|---|---|---|
| 行どうしが独立で、同じ母集団の新しい行を予測する | `rows`、分類なら `stratified` | なし |
| 観測済みでない単位 (新しい国、新しい地点) を予測する | `group` (単位で) | [group](references/group.md) |
| 観測済みでない地域を予測する | `group` (地域で) | [group](references/group.md) |
| 学習データから離れた場所を予測する | `spatial-block` (緩衝帯つき) | [spatial](references/spatial.md) |
| 未来を予測する | `time` | [time](references/time.md) |
| 未来の、離れた場所を予測する | `space-time` | [time](references/time.md) |

## 分割表

`scripts/make_folds.py` は、1 行が (repeat、fold、id、role) の表を Parquet で書く。role は `train` か `test`。その fold に行が無い id は、その fold では使わない (時間の分割で試験の時点より後の行、緩衝帯の中の行)。

```sh
uvx --with duckdb --with scikit-learn --with pyarrow python scripts/make_folds.py \
  tmp/table.parquet ID --scheme group --group region --folds 5 --out tmp/folds_region.parquet
uvx --with duckdb --with scikit-learn python ../spatial-data-modeling/scripts/compare_models.py \
  tmp/table.parquet ID TARGET F1 F2 --task regression --models mean linear hgb \
  --folds-file tmp/folds_region.parquet
```

- 実行すると、fold ごとの学習、試験、未使用の行数と、repeat ごとに試験された行数を出す。
- `rows`、`stratified`、`spatial-block` は repeat ごとに分け方が変わる。`group` と `time` は repeat で変わらず、モデルの乱数の種だけが変わる。
- `compare_models.py` は、分割表の id がデータの行に無いと止まる。分割表と同じ行で採点するため。
- テストは `uvx --with duckdb --with scikit-learn --with pyarrow --with pytest pytest scripts/test_make_folds.py`。緩衝帯の中に学習の行が無いことを総当たりの haversine で、時間の分割で試験の時点以後の行を学習しないことを確かめている。経度と緯度の取り違え、緩衝帯の無視、時間の境界の 1 つずれ、gap の無視のそれぞれで落ちることを確かめてある。

## 分け方でリークが見える

国 × 年の平均寿命を 1 人あたり GDP (対数)、人口 (対数)、都市人口の割合で予測した (WDI、2010〜2022 年、214 か国、2,749 行、2026-10-10):

| 分け方 | 採点した行 | linear の R2 | hgb の R2 |
|---|---:|---:|---:|
| `rows` (行を無作為に) | 2,749 | 0.706 | 0.901 |
| `time` (最後の 3 年を 1 年ずつ) | 629 | 0.696 | 0.842 |
| `group` (国で) | 2,749 | 0.697 | 0.541 |

行を無作為に分けると、ブースティングは同じ国の別の年を学習側に見て、その国を覚えて当てる。国ごと伏せると 0.90 から 0.54 に落ち、線形より悪くなる。線形は分け方によらずほぼ同じ。「データの無い国を埋める」のが使い道なら、正しい評価は `group` で、勝つのは線形。

## 書き出すもの

- モデルの使い道と、選んだ分け方とその理由
- 分割表のファイル、分け方の引数 (fold の数、repeat、ブロックの大きさ、緩衝帯、gap)
- fold ごとの学習、試験、未使用の行数。試験されなかった行の数
- 分け方ごとの点数と、その差から読めること

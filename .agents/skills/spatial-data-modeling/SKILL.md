---
name: spatial-data-modeling
description: 基準 (平均、グループ平均、線形) と同じ分割、同じ指標で、線形、木、ブースティングなどのモデルを当てはめて比べる。回帰と分類の両方。モデルの種類ごとの前処理と落とし穴は references にある。
---

# spatial-data-modeling

モデルの点数は、基準と同じ分割、同じ指標で並べて初めて比べられる。このスキルは、全てのモデルに共通する比べ方を決める。モデルの種類ごとの知識は references にある。

| reference | 中身 |
|---|---|
| [linear-modeling](references/linear-modeling.md) | 線形回帰、Ridge、Lasso、ロジスティック回帰。係数を説明に使うとき |
| [tree-modeling](references/tree-modeling.md) | 決定木、ランダムフォレスト。非線形と相互作用、しきい値 |
| [boosting-modeling](references/boosting-modeling.md) | HistGradientBoosting、XGBoost、LightGBM、CatBoost |
| [foundation-modeling](references/foundation-modeling.md) | TabPFN、TimesFM などの事前学習モデル。版ごとのライセンス |
| [classification](references/classification.md) | 目的変数がカテゴリのときに、どのモデルにも加わる論点 |
| [weights](references/weights.md) | 行ごとの重みで学習し採点する。実効的な標本の数 |
| [error-analysis](references/error-analysis.md) | 誤差をグループや分位ごとに分けて、どこで外れているかを見る |
| [spatial-regression](references/spatial-regression.md) | 残差に空間の偏りが残るときの、空間ラグモデル、空間誤差モデル、空間フィルタ、GWR の選び方 |

言葉:
- 分割表: 交差検証で、どの行を学習に、どの行を試験に使うかを書いたファイル。1 行が 1 つの (repeat、fold、id、role)。repeat は分け直しの回、fold はその回の何番目の分け、id は行の識別子、role は `train` (学習) か `test` (試験)。Parquet (列指向のファイル形式) で書く。
- 基準: `mean` (学習側の平均)、`group_mean` (学習側の同じグループの平均。学習側に無いグループは全体の平均)、分類の `prior` (学習側のクラスの割合)、`linear`。複雑なモデルは、これらを超えて初めて意味がある。

## 手順

1. 問いの種類 (回帰か分類か) と、モデルを何に使うか (予測か、説明か) を書く。説明に使うなら、点数より係数や効き方の安定が大事になる。
2. 試すモデルを先に決める。基準 (mean か prior、group_mean) を必ず含める。
3. 分割は (repeat、fold、id、role の Parquet の) 分割表で決め、基準も同じ分割表で採点する。甘い分け方と厳しい分け方の両方で比べる。
4. 各モデルの前処理を、そのモデルの reference に従って決める。前処理 (標準化、欠損の補完、エンコード) で学習するものは、学習側の行だけで学習する。
5. ハイパーパラメータを決める。決めるなら学習側の中で決める (内側の交差検証か、学習側から取り分けた検証用の行)。試験側の点数を見て選ばない。
6. repeat (乱数の種) を 3 つ以上にして、平均とばらつきを書く。ばらつきより小さい差は差と呼ばない。
7. 基準と並べた表を書く。基準を超えないモデルは、超えないと書く。
8. 選んだモデルの誤差を、地域、時期、測定の回数などで分けて見る (references/error-analysis.md)。
9. 選んだモデルの残差に、空間の偏りが残っていないかを測る (`scripts/error_breakdown.py` に `--lon`、`--lat`、`--k` を付けると、残差の Moran's I と並べ替えの p 値を出す)。偏りが残るなら、行は独立でなく、係数の標準誤差や p 値は小さすぎる。係数を説明に使うなら、空間回帰を検討する (references/spatial-regression.md)。
10. 予測する行が、学習した範囲の内にあるかを確かめる (適用領域)。特徴量ごとに学習側の範囲 (最小と最大) を外れる行の数と、特徴量を標準化した空間で最も近い学習側の行までの距離を、交差検証の試験側の行と比べる。木やブースティングは範囲の外で平らになり、線形は範囲の外へ直線を延ばす。座標を特徴量に入れたモデルを、学習に無い地域に当てるのは外挿で、その行は分けて報告する。

## 比べる仕組み

`scripts/compare_models.py` は、分割表 (`--folds-file`) を読み、全てのモデルを同じ fold で採点する。repeat ごとに、試験された各行を、その行を学習に使わなかったモデルで 1 回予測し、まとめて採点する。どの fold でも試験されない行 (時間の分割の最初の時点) は採点から外し、採点した行の数を `n` に出す。repeat の番号はモデルの乱数の種にもなる。調整するもの (Ridge の罰則、ブースティングの早期打ち切り) は学習側の中で決める。

```sh
uvx --with duckdb --with scikit-learn python scripts/compare_models.py tmp/table.parquet ID TARGET F1 F2 F3 \
  --task regression --models mean group_mean linear ridge rf hgb --group region \
  --folds-file tmp/folds_region.parquet
```

`--predictions-out FILE` (`--with pyarrow` が要る) で、交差検証の外側の予測を (repeat、model、id、target、prediction) の表に書き出す。残差の空間自己相関や較正に使う。

表は、使う列に欠損の無い行だけにしておく。分割表もその表から作る。分割表の id がデータの行に無いと止まる。

分類は `--task classification` で、目的変数は 0/1。基準は `prior` (学習側のクラスの割合)。

テストは `uvx --with duckdb --with scikit-learn --with pytest pytest scripts/test_compare_models.py`。学習データを丸暗記するモデルで、試験側の行が学習に入っていないことを確かめている。全行で学習する、グループ平均を学習側から取らない、1 つの repeat で同じ行を 2 回試験する、試験されない行を採点に入れる、のそれぞれで落ちることを確かめてある。

## 単純なモデルが勝つこともある

複雑なモデルが基準や線形に勝つとは限らない。たとえば国 × 1 年の平均寿命を 1 人あたり GDP (対数)、人口 (対数)、都市人口の割合で予測すると (WDI、2022 年、209 か国、種 3 つの平均、2026-10-10):

| モデル | R2 (行を無作為に 5 分割) | R2 (地域ごとに 5 分割) |
|---|---:|---:|
| mean | -0.011 | -0.344 |
| linear | 0.631 | 0.521 |
| rf | 0.518 (sd 0.06) | 0.337 |
| hgb | 0.580 | 0.324 |
| tabpfn_v2 | 0.624 | 0.484 |

木とブースティングと TabPFN は、どちらの分割でも線形に負けた。地域ごとの分割では差が開く。試験側の行が学習側の特徴量の範囲の外に出たのは 209 行中 8 行だけで、その 8 行ではランダムフォレストの RMSE が 7.88、線形が 4.92。範囲の内側の 201 行でも 6.40 と 5.50 で、外挿だけでは差を説明できない。行数が少なく、関係が滑らかで単調なことが効いていると推測している (未確認)。

## 書き出すもの

- 問いの種類と、予測か説明か
- 分割 (行か、グループか、何で分けたか)、分割の数、乱数の種
- モデルごとの前処理と、調整したハイパーパラメータとその決め方
- モデル × 分割ごとの指標の平均とばらつき。基準を含める
- 勝ったモデルと、その差がばらつきより大きいか

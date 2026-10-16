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
| [classification](references/classification.md) | 目的変数がカテゴリのときに、どのモデルにも加わる論点。多クラスの指標、稀なクラス、argmax、空間的に固まったクラス |
| [panel-data](references/panel-data.md) | 同じ単位を繰り返し観測したデータ。単位と時間の固定効果、時間で変わらない変数、クラスタの標準誤差、ラグ (`scripts/panel_fit.py`) |
| [multilevel-models](references/multilevel-models.md) | 入れ子の構造 (地点、市区町村、都道府県)。部分的なまとめと縮小、ICC、ランダム傾き、上の段を落とす誤り、Mundlak (`scripts/multilevel_fit.py`) |
| [bayesian-modeling](references/bayesian-modeling.md) | 事前、尤度、事後、事後予測を解析的に解ける小さいモデルで。事前予測と事前分布の感度、事後予測の確かめ、信用区間と信頼区間、階層モデルとの対応 (`scripts/bayes_conjugate.py`) |
| [measurement-error](references/measurement-error.md) | 観測値が潜在的な真値の雑音まじりの代わりのとき。古典的と Berkson の誤差、減衰と信頼性、繰り返しと検証用の標本、回帰による較正、誤分類 (`scripts/measurement_error.py`) |
| [weights](references/weights.md) | 行ごとの重みで学習し採点する。実効的な標本の数 |
| [error-analysis](references/error-analysis.md) | 誤差をグループや分位ごとに分けて、どこで外れているかを見る |
| [regression-diagnostics](references/regression-diagnostics.md) | 係数を説明や検定に使うときの、残差の広がり (Breusch-Pagan、White)、形 (Jarque-Bera)、計画行列の条件数、HC3 の標準誤差 (`scripts/regression_diagnostics.py`)。予測の点数で比べるだけなら要らない |
| [spatial-regression](references/spatial-regression.md) | 残差に空間の偏りが残るときの、空間ラグモデル、空間誤差モデル、空間フィルタ、GWR の選び方。ラグと誤差の最尤、LM 検定、直接効果と間接効果 (`scripts/spatial_regression.py`) |
| [gwr](references/gwr.md) | 係数が場所で違うかを見る地理的加重回帰。核と帯域、AICc の曲線、tr(S)、調整した臨界の t、局所の傾きが共線で動くこと (`scripts/gwr.py`) |
| [count-modeling](references/count-modeling.md) | 件数と率: ポアソン回帰と offset、発生率比、過分散と負の二項、ゼロが多いとき (合成データの比較) |
| [compositional](references/compositional.md) | 合計が一定の割合 (土地利用、年齢、産業の構成): 閉包、共線性、基準のカテゴリ、対数比、0 の扱い |

言葉:
- 分割表: 交差検証で、どの行を学習に、どの行を試験に使うかを書いたファイル。1 行が 1 つの (repeat、fold、id、role)。repeat は分け直しの回、fold はその回の何番目の分け、id は行の識別子、role は `train` (学習) か `test` (試験)。Parquet (列指向のファイル形式) で書く。
- 基準: `mean` (学習側の平均)、`group_mean` (学習側の同じグループの平均。学習側に無いグループは全体の平均)、分類の `prior` (学習側のクラスの割合)、`linear`。複雑なモデルは、これらを超えて初めて意味がある。

## 手順

1. 問いの種類 (回帰か分類か) と、モデルを何に使うか (予測か、説明か) を書く。説明に使うなら、点数より係数や効き方の安定が大事になる。 因果の効果を知りたいなら、高い点数も、係数や p 値も、識別の根拠にならない。モデルを選ぶ前に、処置、推定の対象、調整する変数としてはいけない変数を決め、特徴量はその調整の集合に限る。
2. 試すモデルを先に決める。基準 (mean か prior、group_mean) を必ず含める。
3. 分割は (repeat、fold、id、role の Parquet の) 分割表で決め、基準も同じ分割表で採点する。甘い分け方と厳しい分け方の両方で比べる。
4. 各モデルの前処理を、そのモデルの reference に従って決める。前処理 (標準化、欠損の補完、エンコード) で学習するものは、学習側の行だけで学習する。
5. ハイパーパラメータを決める。決めるなら学習側の中で、外側の分割と同じ依存の構造を保った内側の分割で決める。地域を伏せて評価するなら内側でも地域を伏せ、未来を予測するなら内側でも過去で当てて後の期間で選ぶ。学習側から無作為に取った検証用の行は、同じ地域や同じ時期の行と近く、未知の地域や未来に効く設定を選ばない。前処理 (標準化、補完) からモデルの選択までを内側の分割の中に収める。試験側の点数を見て選ばない。
6. repeat (乱数の種) を 3 つ以上にして、平均とばらつきを書く。ばらつきより小さい差は差と呼ばない。
7. 基準と並べた表を書く。基準を超えないモデルは、超えないと書く。
8. 選んだモデルの誤差を、地域、時期、測定の回数などで分けて見る (references/error-analysis.md)。
9. 選んだモデルの残差に、空間の偏りが残っていないかを測る (`scripts/error_breakdown.py` に `--lon`、`--lat`、`--k` を付けると、残差の Moran's I と並べ替えの p 値を出す)。偏りが残るなら、行は独立でなく、係数の標準誤差や p 値は小さすぎる。係数を説明に使うなら、空間回帰を検討する (references/spatial-regression.md)。
10. 予測する行が、学習した範囲の内にあるかを確かめる (適用領域)。特徴量ごとに学習側の範囲 (最小と最大) を外れる行の数と、特徴量を標準化した空間で最も近い学習側の行までの距離を、交差検証の試験側の行と比べる。木やブースティングは範囲の外で平らになり、線形は範囲の外へ直線を延ばす。座標を特徴量に入れたモデルを、学習に無い地域に当てるのは外挿で、その行は分けて報告する。

## 比べる仕組み

`scripts/compare_models.py` は、分割表 (`--folds-file`) を読み、全てのモデルを同じ fold で採点する。repeat ごとに、試験された各行を、その行を学習に使わなかったモデルで 1 回予測し、まとめて採点する。どの fold でも試験されない行 (時間の分割の最初の時点) は採点から外し、採点した行の数を `n` に出す。repeat の番号はモデルの乱数の種にもなる。

調整するもの (ridge の罰則、hgb の木の数) は、外側の fold k の学習側の行の中で、分割表から作った内側の分割で選ぶ。他の fold j ごとに、「fold j の学習の行」で当て「fold j の試験の行」で測り、どちらも fold k の学習の行に限る。地域や空間ブロックを伏せること、緩衝帯、過去だけで学習することが、内側にもそのまま引き継がれる。標準化は候補ごとの pipeline の中にあり、内側の学習の行で当てる。時間の分割の最初の fold には、学習の行の中に他の fold が無いので、`--inner-time 列` を付ける。すると内側は、学習の行の最後の `--inner-folds` (既定 3) 個の期間を 1 つずつ検証に使い、それより前の期間 (`--inner-gap` 個の期間を空ける) で当てる。`--inner-time` は空間を見ないので、時空間の分割では内側で地域は伏せない。時間と空間の両方を保つ内側の分割は未対応。

WDI の 2022 年の平均寿命 (209 か国、5 fold、2026-10-16) で、地域で伏せた同じ分割表を新旧の版で測ると、hgb は、学習側の無作為な 1 割で打ち切っていた以前の版の R2 0.324 から 0.359 になった。ridge は、内側で地域を伏せると罰則が候補の最小 (0.001) に決まり、線形回帰と同じ 0.521 になった (以前の版は 0.520)。

```sh
uvx --with duckdb --with scikit-learn python scripts/compare_models.py tmp/table.parquet ID TARGET F1 F2 F3 \
  --task regression --models mean group_mean linear ridge rf hgb --group region \
  --folds-file tmp/folds_region.parquet
```

`--predictions-out FILE` (`--with pyarrow` が要る) で、交差検証の外側の予測を (repeat、model、id、target、prediction) の表に書き出す。残差の空間自己相関や較正に使う。

表は、使う列に欠損の無い行だけにしておく。分割表もその表から作る。分割表の id がデータの行に無いと止まる。

分類は `--task classification` で、目的変数が 0/1 なら二値、それ以外のラベルなら多クラス (macro F1、balanced accuracy、クラスごとの precision と recall も出す)。基準は `prior` (学習側のクラスの割合)。

テストは `uvx --with duckdb --with scikit-learn --with pytest pytest scripts/test_compare_models.py`。学習データを丸暗記するモデルで、試験側の行が学習に入っていないことを確かめている。全行で学習する、グループ平均を学習側から取らない、1 つの repeat で同じ行を 2 回試験する、試験されない行を採点に入れる、のそれぞれで落ちることを確かめてある。内側の分割が外側の試験の行を含まず、グループを内側でも伏せ、時間の分割では過去だけを見ること、グループの特徴を覚えれば当たる合成データで、内側で地域を伏せると ridge の罰則が大きく、hgb の木の数が少なく選ばれることも確かめ、内側を無作為に分ける、標準化を候補の外に出す、内側の学習から fold j の学習の制限を外す、学習の行の一部だけで当て直す、のそれぞれで落ちることを確かめてある。

## 単純なモデルが勝つこともある

複雑なモデルが基準や線形に勝つとは限らない。たとえば国 × 1 年の平均寿命を 1 人あたり GDP (対数)、人口 (対数)、都市人口の割合で予測すると (WDI の版 2026-10-01、2022 年、209 か国、`make_folds.py` の分割表で 5 fold、repeat 0、1、2 の平均、scikit-learn 1.9.1、d133d92 の版、2026-10-16):

| モデル | R2 (行を無作為に 5 分割) | R2 (地域ごとに 5 分割) |
|---|---:|---:|
| mean | -0.011 | -0.344 |
| linear | 0.627 | 0.521 |
| ridge | 0.627 | 0.521 |
| rf | 0.540 (sd 0.04) | 0.335 |
| hgb | 0.567 (sd 0.02) | 0.359 |

木とブースティングは、どちらの分割でも線形に負けた。地域ごとの分割では差が開く。地域ごとの分割では、ridge は内側で罰則が候補の最小 (0.001) に決まり、線形と同じになった。

以前の表 (2026-10-10、分割表の仕組み c7830d6 より前の実装、乱数の種 3 つ。hgb は学習側の無作為な 1 割で早期打ち切り) は次のとおりで、今の分割表とは分け方が違う。同じ条件では測り直していない。

| モデル | R2 (行を無作為に 5 分割) | R2 (地域ごとに 5 分割) |
|---|---:|---:|
| mean | -0.011 | -0.344 |
| linear | 0.631 | 0.521 |
| rf | 0.518 (sd 0.06) | 0.337 |
| hgb | 0.580 | 0.324 |
| tabpfn_v2 | 0.624 | 0.484 |

以前の表で、試験側の行が学習側の特徴量の範囲の外に出たのは 209 行中 8 行だけで、その 8 行ではランダムフォレストの RMSE が 7.88、線形が 4.92。範囲の内側の 201 行でも 6.40 と 5.50 で、外挿だけでは差を説明できない。行数が少なく、関係が滑らかで単調なことが効いていると推測している (未確認)。

## 書き出すもの

- 問いの種類と、予測か説明か
- 分割 (行か、グループか、何で分けたか)、分割の数、乱数の種
- モデルごとの前処理と、調整したハイパーパラメータとその決め方
- モデル × 分割ごとの指標の平均とばらつき。基準を含める
- 勝ったモデルと、その差がばらつきより大きいか

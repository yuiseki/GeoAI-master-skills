---
name: model-explanation
description: モデルが何に頼って予測しているかを、採点と同じ分割表の、学習に使わなかった行で調べる。permutation importance (群でも)、部分依存。分割表を変えて重要度を比べ、位置や単位を覚えているだけの特徴量を見分ける。モデルを選んだ後、結論を言葉にする前に使う。
---

# model-explanation

説明はモデルの説明であって、世界の説明ではない。重要度が高いことは、その特徴量が目的変数の原因であることを意味しない。モデルがその特徴量に頼っていることだけを意味する。

| reference | 何を見るか |
|---|---|
| [permutation](references/permutation.md) | 特徴量 (や特徴量の群) を並べ替えたとき、点数がどれだけ落ちるか |
| [partial-dependence](references/partial-dependence.md) | 1 つの特徴量を動かしたとき、予測の平均がどう動くか |

## 手順

1. 説明したいモデルと、本番の使い道に合った分割表を決める (分割表は、どの行を学習に、どの行を試験に使うかを書いた Parquet。1 行が repeat、fold、id、role で、role は `train` か `test`)。
2. `scripts/explain_model.py importance` で、各 fold の試験側の行で重要度を測る。相関の強い特徴量 (緯度と経度、似た指標) は `--group` でまとめても測る。
3. 甘い分割表 (行を無作為に) でも測り、重要度を比べる。甘い分割表でだけ重要な特徴量は、単位や場所を覚えるのに使われている。
4. 重要な特徴量について、`scripts/explain_model.py pd` で部分依存を見る。向きと形 (直線、飽和、しきい値) を言葉にする。 `ice` で行ごとの曲線も見て、行によって向きが逆になっていないかを確かめる。
5. 線形モデルの係数や、別のモデルの部分依存と並べる。モデルによって形が違うなら、どちらかの形はデータの少ない所の当て推量。
6. 書き出す。

```sh
uvx --with duckdb --with scikit-learn python scripts/explain_model.py importance \
  tmp/table.parquet ID TARGET F1 F2 lon lat --task regression --model hgb \
  --folds-file tmp/folds_region.parquet --group lonlat=lon,lat
uvx --with duckdb --with scikit-learn python scripts/explain_model.py pd \
  tmp/table.parquet ID TARGET F1 F2 lon lat --task regression --model hgb \
  --folds-file tmp/folds_rows.parquet --feature F1
```

モデルと分割表の読み込みは、同じ場所の `compare_models.py` を使う。

テストは `uvx --with duckdb --with scikit-learn --with pytest pytest scripts/test_explain_model.py`。目的変数に関係する特徴量だけが重要になること、学習側の行で測ると雑音の特徴量まで重要に見えること、相関の強い 2 つの特徴量をまとめて並べ替えると組を保ったまま壊れること、部分依存が関係の形 (2 次曲線) をたどることを確かめている。学習側の行で測る、群を別々に並べ替える、のそれぞれで落ちることを確かめてある。

## 重要度は因果の効果ではない

予測モデルの特徴量の重要度や部分依存は、そのモデルが予測にどの特徴量を使ったかで、特徴量を変えたら結果が変わるかではない。相関する特徴量の一方だけが重く見え、交絡する特徴量や、結果の言い換えに近い特徴量も重く出る。重要度を「その要因の効果」と書かない。効果を言うには、原因と結果の構造を描いて、それに合う推定をする。

## 書き出すもの

- 説明したモデルと分割表、比べた甘い分割表
- 重要度 (平均とばらつき) を分割表ごとに、群の重要度も
- 重要な特徴量の部分依存の向きと形、モデルの間の違い
- 言えないこと (因果、データの少ない範囲の形)

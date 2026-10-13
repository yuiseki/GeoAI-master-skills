# 入門: 1 つの問いを最初から最後まで

国の平均寿命を、経済と人口の指標から予測する。この問いを、データを知るところから、評価を疑うところまで通す。画面の出力は、版 2026-10-01 の WDI で実際に流した結果 (2026-10-11)。

QGIS の画面操作ではなく、コードを書いて分析する。以下のコードは、そのまま写して流せる。

必要なもの: `uv` (Python の環境を用意しなくてよくなる)。以下の `uvx` は、その場で必要なライブラリを入れて動かす。リポジトリの直下で流す。

この機械では、重い処理がメモリを使い切って機械ごと止まることがあるので、実データの実行には上限を付ける (`.agents/skills/AGENTS.md` の「スクリプト」)。この入門の処理は軽いので、付けなくてもよい。

## 0. 問いを決める

「国の平均寿命 (2022 年) を、1 人あたり GDP、人口、都市人口の割合から予測する」。使い道は、「平均寿命のデータが無い国の値を埋める」とする。使い道は、後で評価の分け方を決めるときに効く。

## 座標の基礎: 度は距離ではない

地理のデータの座標は、経度と緯度 (度) で付いていることが多い。度は角度で、距離ではない。緯度が高いほど、経度 1 度の長さは短くなる。

```sh
uvx --with numpy python docs/tutorial/crs_demo.py
```

```
緯度    経度1度(km)   緯度1度(km)   格子の面積(km2)
  0度       111.2         111.2           12364
 35度        91.1         111.2           10128
 60度        55.6         111.2            6182
 80度        19.3         111.2            2147

オスロからヘルシンキ (経度, 緯度の順に渡す): 787 km
オスロからヘルシンキ (緯度, 経度を取り違えた): 1578 km
```

- 1 度 × 1 度の格子の面積は、緯度 60 度で赤道の半分ほどになる。度で切った格子で件数を比べると、高緯度ほど面積が小さい。面積か人口で割るかを決める。
- 座標の順は、経度が先か緯度が先かがツールごとに違う。取り違えると、エラーにならずに別の距離が出る。ここでは 787 km が 1578 km になった。小さな例で、既知の 2 点の距離と合うかを確かめる。
- CRS (座標参照系) は、座標の数字が地球上のどこかを決める約束。結合する前に、両方の CRS を確かめる。用語は [glossary](../glossary.md)。

## 1. データを知る (スキル dataset-discovery)

WDI (世界銀行の開発指標) を使う。国 × 年 × 指標の縦持ちの表で、座標は無い。国のほかに、World や地域の集計も同じ表に入っている。国だけに絞る必要がある。

```sh
uvx --from 'duckdb>=1.5.5' python docs/tutorial/run_sql.py docs/tutorial/wdi_2022.sql
```

```
countries  with_life  with_gdp  with_pop  with_urban  complete
      217        217       209       217         217       209
```

- 国は 217 か国。1 人あたり GDP が無い国が 8 か国あり、4 つの指標が全て揃うのは 209 か国。
- 欠ける国は無作為ではない (紛争中や閉鎖的な国と小さな領土)。単に除くと、紛争や貧困についての結論が偏りうる。ここでは除いて、除いたことを書く。
- 使った版 (2026-10-01) を書いておく。WDI は版の間で過去の値も改訂される。

## 2. 分析の単位を決める (スキル analysis-unit-design)

1 行は「1 つの国の 2022 年」。標本は 209 行しかない。件数が少ないので、点数の揺れは大きい。

## 3. 目的変数を見る (スキル eda-and-baseline)

```sh
uvx --from 'duckdb>=1.5.5' python -c "
import duckdb
duckdb.sql(\"copy (select * from 'tmp/wdi_2022.parquet' where life_exp is not null and log_gdp_pc is not null) to 'tmp/wdi_2022_complete.parquet' (format parquet)\")
print(duckdb.sql(\"select count(*) n, round(min(life_exp),1) lo, round(median(life_exp),1) med, round(max(life_exp),1) hi from 'tmp/wdi_2022_complete.parquet'\"))"
```

```
n=209, 最小 18.8, 中央値 74.2, 最大 85.7
```

最小の 18.8 歳は極端に低い。中央アフリカ共和国 (`CAF`) の値で、この版では同じ国の 2017〜2022 年が 18.8〜45.2 歳と年ごとに大きく上下する。古い版 (2024-05-30) では 53.5〜55.0 歳で滑らか。版による系列の荒れで、データの誤りの疑いがある (dataset-discovery の WDI の reference に実測がある)。外れ値は、消す前に原因を調べて、消したかどうかを書く。ここでは残す。

## 4. 基準を出す (スキル eda-and-baseline)

複雑なモデルを試す前に、単純な予測の点数を出す。ここで 2 通りの分け方を比べる。

- 行を無作為に分ける (`--cv rows`): 試験側の国のすぐ隣の国が、学習側にいる。
- 地域ごと伏せる (`--cv group`): 試験側の地域の国が、学習側に 1 つもいない。

「データの無い国を埋める」使い道に近いのは、どちらか。

```sh
for cv in rows group; do
  uvx --with duckdb --with scikit-learn python .agents/skills/eda-and-baseline/scripts/score_folds.py \
    tmp/wdi_2022_complete.parquet iso3 life_exp log_gdp_pc log_pop urban_pct \
    --task regression --models mean group_mean linear --cv $cv --group region --repeats 3
done
```

| 基準 | 行を無作為に (R2) | 地域ごと伏せる (R2) |
|---|---:|---:|
| mean (学習側の平均) | -0.011 | -0.344 |
| group_mean (学習側の同じ地域の平均) | 0.464 | -0.344 |
| linear (線形回帰) | 0.627 | 0.521 |

R2 は、平均で予測した場合を 0 として、どれだけ良いかを表す (1 が完全、負は平均より悪い)。

- 地域ごと伏せると、全体の平均すら大きく外れる (R2 -0.34)。試験側の地域の水準が、学習側と違うため。
- group_mean は、地域ごと伏せると mean と同じになる。試験側の地域は学習側に無いので、平均に戻る。
- 線形回帰は、どちらの分け方でも 0.5〜0.6 を保つ。

## 5. モデルを足して、同じ分け方で比べる (スキル spatial-data-modeling、cross-validation-design)

木のモデル (勾配ブースティング、`hgb`) を足す。

```sh
for cv in rows group; do
  uvx --with duckdb --with scikit-learn python .agents/skills/eda-and-baseline/scripts/score_folds.py \
    tmp/wdi_2022_complete.parquet iso3 life_exp log_gdp_pc log_pop urban_pct \
    --task regression --models linear hgb --cv $cv --group region --repeats 3
done
```

| モデル | 行を無作為に (R2) | 地域ごと伏せる (R2) |
|---|---:|---:|
| linear | 0.627 | 0.521 |
| hgb | 0.558 | 0.342 |

- この小さな表では、hgb は線形に勝てない。どちらの分け方でも線形が上。
- hgb は、地域ごと伏せると 0.558 から 0.342 に落ちる。同じ地域の国を学習側に見て覚えていた分が、使えなくなったため。線形は 0.627 から 0.521 で、落ち方が小さい。
- 「データの無い国を埋める」なら、地域ごと伏せた点数を信じる。行を無作為に分けた点数で選ぶと、実際より良いモデルだと思い込む。

scikit-learn だけで同じ比べ方をするなら、`KFold` を `GroupKFold` に替えて、`groups` に地域を渡す。

```sh
uvx --with duckdb --with scikit-learn --with pandas --with pyarrow python docs/tutorial/kfold_vs_group.py tmp/wdi_2022_complete.parquet
```

```
KFold (行を無作為に)           linear  R2 0.638
KFold (行を無作為に)           hgb     R2 0.571
GroupKFold (地域ごと伏せる)     linear  R2 0.521
GroupKFold (地域ごと伏せる)     hgb     R2 0.342
```

`cross_val_predict` は、各行を、その行を学習に使わなかったモデルで予測する (交差検証の外側の予測)。`KFold` の数字が上の表と少し違うのは、分け方の乱数が違うため。分け方を `GroupKFold` に替えただけで、木のモデルは 0.571 から 0.342 に落ちる。

もっと大きな表 (国 × 年の 2,749 行) では、木のモデルは行を無作為に分けると線形を大きく上回り (R2 0.91 と 0.71)、国ごと伏せると逆転する (0.55 と 0.70)。同じ国の別の年を覚えるため。cross-validation-design の SKILL.md に実例がある。

## 6. ここから先

この入門で扱ったのは、データを知る、単位を決める、基準を出す、評価の分け方を疑う、までの一巡。続きは問いに応じて選ぶ。

| 知りたいこと | スキル |
|---|---|
| 点数が良すぎる。リークではないか | leakage-audit |
| どこまで良くなりうるか (測定の雑音の天井) | noise-ceiling-analysis |
| 予測の不確かさ、区間 | uncertainty-estimation |
| どの特徴量がどう効いているか | model-explanation |
| 近い国どうしで値が似ているか。残差に空間の偏りが残っていないか | spatial-autocorrelation |
| 単位や格子の大きさで結論が変わらないか | robustness-analysis |

全体の流れは `AGENTS.md` (リポジトリ直下)、用語は `docs/glossary.md`。

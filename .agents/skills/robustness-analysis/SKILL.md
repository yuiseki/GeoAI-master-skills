---
name: robustness-analysis
description: 分析の結論を確かめられる式で書き、乱数の種、標本、集計の単位 (MAUP)、手法の設定、データの版、影響の大きい単位の有無を変えて、結論が保たれるかを試す。探索で見つけた構造が設定を変えても残るかにも使う。結論を報告する前に使う。
---

# robustness-analysis

結論は、それを導いた 1 つの条件の産物かもしれない。条件を変えて結論が保たれれば、その範囲で結論を言える。崩れれば、崩れた条件を結論に添える。

| reference | 中身 |
|---|---|
| [maup](references/maup.md) | 集計の単位 (格子の大きさ、行政区の階層) で結果が変わる問題 |

## 手順

1. 結論を、出力の数字で確かめられる式で書く。「線形が hgb より良い」なら `linear > hgb`、「残差に自己相関は無い」なら `abs(i) < 0.05`。
2. 変える条件を選ぶ (下の表)。結論を導いた条件のうち、別の選び方もありえたもの全て。
3. `scripts/robustness_grid.py` で、条件の全ての組み合わせについて、これまでのスキルのコマンドを流し、結論が保たれるかを表にする。
4. 崩れた条件を読む。崩れ方に筋があるか (細かい格子でだけ崩れる、ある地域を除くと崩れる)。
5. 結論を、保たれた範囲に合わせて書き直す。

## 変える条件

| 条件 | 例 | 使うスキル |
|---|---|---|
| 乱数の種 | repeat を増やす | cross-validation-design、spatial-data-modeling |
| 分け方 | 行、グループ、空間ブロック、時間 | cross-validation-design |
| 標本 | 単位の 8 割を抜き出して繰り返す | clustering-analysis の安定性 |
| 影響の大きい単位 | 外れた単位を除く | anomaly-detection |
| 集計の単位 (MAUP) | 格子の大きさ、行政区の階層 | analysis-unit-design、references/maup.md |
| 手法の設定 | 近傍の数、距離の帯、群の数、モデルの種類 | 各スキル |
| データの版 | WDI の版、OSM の凍結日 | dataset-discovery |
| 既知の区分 | 見つけた群や外れが、地域や所得階層をなぞっているだけか | clustering-analysis、spatial-autocorrelation |

## 使い方

```sh
python scripts/robustness_grid.py \
  --vary table=wdi_2022,wdi_2022_nocaf --vary scheme=rows,group,spatial-block \
  --step "uvx ... make_folds.py tmp/{table}.parquet iso3 --scheme {scheme} --group region --lon lon --lat lat --block-km 2000 --out tmp/f_{table}_{scheme}.parquet" \
  --step "uvx ... compare_models.py tmp/{table}.parquet iso3 life_exp F1 F2 F3 --task regression --models linear hgb --folds-file tmp/f_{table}_{scheme}.parquet" \
  --extract "linear=^linear .*r2 ([-0-9.e]+)" --extract "hgb=^hgb .*r2 ([-0-9.e]+)" \
  --claim "linear > hgb"
```

- `--step` の `{名前}` は `--vary` の値に置き換わる。条件ごとに出力ファイルの名前を変える。
- 数字は最後の `--step` の出力から `--extract` の正規表現で抜き出す。抜き出せなければ止まる。数字が無いことを、結論が保たれたことにしない。
- `--claim` に書けるのは、抜き出した名前、数、四則、比較、and、or、not、abs、min、max だけ。

テストは `uvx --with pytest pytest scripts/test_robustness_grid.py`。抜き出せないときと、コマンドが失敗したときに止まること、結論の式で任意のコードを動かせないことを確かめている。それぞれを外すと落ちることを確かめてある。

## 実例

WDI の 2022 年の平均寿命で、「線形が hgb より良い」を、中央アフリカ共和国の有無 × 分け方 3 通りで試した (2026-10-10)。6 条件の全てで保たれた。

| 表 | 分け方 | 線形の R2 | hgb の R2 |
|---|---|---:|---:|
| 207 か国 | 行を無作為に | 0.627 | 0.576 |
| 207 か国 | 地域で | 0.524 | 0.338 |
| 207 か国 | 2,000 km の空間ブロック | 0.614 | 0.542 |
| 中央アフリカ共和国を除く | 行を無作為に | 0.703 | 0.651 |
| 中央アフリカ共和国を除く | 地域で | 0.608 | 0.408 |
| 中央アフリカ共和国を除く | 2,000 km の空間ブロック | 0.687 | 0.640 |

点数の大きさは条件で 0.1 以上動くが、順位は変わらない。「この表では線形が勝つ」は言え、「R2 は 0.6 を超える」は言えない (地域で分けると 0.52)。

## 書き出すもの

- 結論の式
- 変えた条件と、その値
- 条件ごとの数字と、保たれたか
- 保たれた範囲に合わせて書き直した結論

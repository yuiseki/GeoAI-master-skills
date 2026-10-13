---
name: uncertainty-estimation
description: モデルの不確かさを信じてよいかを確かめる。分類なら確率の較正 (Brier、ECE、信頼性の表)、回帰なら予測区間 (共形予測) とその被覆率。全体だけでなく、地域や年などのグループごとに見る。予測を確率や区間として使う前に使う。
---

# uncertainty-estimation

確率や区間は、全体で約束を守っていても、特定のグループで守っていないことがある。全体の数字に加えて、本番で使う単位のグループごとに確かめる。

| reference | 対象 |
|---|---|
| [calibration](references/calibration.md) | 分類の確率。モデルが 0.3 と言った行の 3 割が陽性か |
| [intervals](references/intervals.md) | 回帰の予測区間。90% の区間が 9 割の行を覆うか |

## 手順

1. 予測をどう使うかを書く。確率をそのまま使うのか、しきい値で 0/1 にするのか、区間で幅を示すのか。
2. spatial-data-modeling の `compare_models.py --predictions-out` で、交差検証の外側の予測を書き出す。学習に使った行の予測では、不確かさを小さく見積もる。
3. `scripts/uncertainty.py` で、全体と、グループ (`--by`、地域、年、所得階層など) ごとに確かめる。
4. ずれていたら、その原因を探す。時代による基準の割合のずれか、特定のグループの雑音の大きさか、モデルの癖か。
5. 直すなら、学習側の中で較正する、グループごとに区間を作る、などを行い、同じ分割表で確かめ直す。
6. 書き出す。

```sh
uvx --with duckdb --with scikit-learn python scripts/uncertainty.py calibration tmp/predictions.parquet \
  --table tmp/table.parquet --id ID --by year
uvx --with duckdb --with scikit-learn python scripts/uncertainty.py intervals tmp/predictions.parquet \
  --table tmp/table.parquet --id ID --by region --alpha 0.1
```

テストは `uvx --with duckdb --with scikit-learn --with pytest pytest scripts/test_uncertainty.py`。ECE を手で計算できる例と一致すること、Brier が scikit-learn と一致すること、区間が約束どおりの割合を覆うこと、各行の区間が自分の残差を使わないこと (同じ値の多いデータで総当たりと一致)、雑音の大きいグループで区間が狭すぎることを示せることを確かめている。自分の残差を使う、ECE の重みを落とす、のそれぞれで落ちることを確かめてある。

## 書き出すもの

- 予測の使い方と、確かめた分割表
- 分類: Brier、ECE、信頼性の表を、全体とグループごとに
- 回帰: 約束した割合、全体とグループごとの被覆率、区間の幅
- ずれの原因の見立てと、直したならその方法と結果
